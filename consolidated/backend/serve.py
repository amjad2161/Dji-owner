"""
SkyCore live backend — driven by REAL skycore algorithms.

Serves telemetry + flight commands (ws /ws/telemetry) and a threat feed
(ws /ws/threats) in the shapes the SkyCore GCS expects.

HONEST design — a physics-lite SIMULATOR generates ground truth; three GENUINE
skycore modules run in the live loop:
  - navigation: 22-state Adaptive UKF (skycore/navigation/aukf.py) filters noisy GPS.
  - control:    LQRController (skycore/control/lqr.py) flies the aircraft closed-loop
                (point-mass double-integrator in ENU metres).
  - detection:  CUASClassifier (skycore/cuas/classifier.py) classifies a SIMULATED
                intruder track into a severity-graded threat for the GCS Threats page.
Every frame is tagged source="simulator" and reports which real backend is active.
No physical drone / real RF sensing is claimed. If any real module can't import or
goes non-finite, we fall back and say so (backend name reflects it). Detection/alerting
only — no jamming / countermeasure capability.

Run:  python serve.py
Deps: fastapi, uvicorn[standard], numpy, scipy
Env:  SKYCORE_PKG=<path to skycore package dir> to override module discovery.
"""
from __future__ import annotations

import asyncio
import math
import os
import random
import sys
import time

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

try:
    import numpy as np
except Exception:
    np = None

# --- locate the real skycore package and import its modules directly (avoids
#     package __init__ side effects), mirroring the honest provenance pattern. ---
_here = os.path.dirname(os.path.abspath(__file__))
_PKG_CANDIDATES = [
    os.environ.get("SKYCORE_PKG", ""),
    os.path.join(_here, "..", "..", "src", "skycore_v1.0.0", "skycore"),
    os.path.join(_here, "..", "src", "skycore_v1.0.0", "skycore"),
    r"C:\Users\Mobar\OneDrive\Desktop\SkyCore_Consolidated\src\skycore_v1.0.0\skycore",
]
AdaptiveUKF = LQRController = CUASClassifier = ThreatFeatures = None
NAV_BACKEND = CTRL_BACKEND = DETECT_BACKEND = "unavailable"
if np is not None:
    for _pkg in _PKG_CANDIDATES:
        if _pkg and os.path.isdir(_pkg):
            for _sub in ("navigation", "control", "cuas"):
                sys.path.insert(0, os.path.join(_pkg, _sub))
            try:
                from aukf import AdaptiveUKF  # type: ignore
                NAV_BACKEND = "skycore.navigation.aukf.AdaptiveUKF (22-state)"
            except Exception:
                AdaptiveUKF = None
            try:
                from lqr import LQRController  # type: ignore
                CTRL_BACKEND = "skycore.control.lqr.LQRController (point-mass ENU)"
            except Exception:
                LQRController = None
            try:
                from classifier import CUASClassifier, ThreatFeatures  # type: ignore
                DETECT_BACKEND = "skycore.cuas.classifier.CUASClassifier (rule-based)"
            except Exception:
                CUASClassifier = None
            break

HOME_LAT, HOME_LON = 32.0853, 34.7818
TICK_HZ = 10.0
FDT = 1.0 / TICK_HZ           # fixed dt for control/plant discretisation
ACCEL_CLIP = 4.0              # m/s^2, keeps motion drone-like
CLIMB_RATE = 2.5             # m/s, naive-fallback only
CRUISE_SPEED = 9.0          # m/s, naive-fallback only
BATTERY_DRAIN = 0.06
GPS_NOISE_H, GPS_NOISE_V = 1.2, 0.6
INTRUDER_SPEED = 12.0
MAX_H_SPEED = 16.0           # m/s horizontal velocity envelope (drone-like)
MAX_V_SPEED = 4.0           # m/s vertical velocity envelope
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LON = M_PER_DEG_LAT * math.cos(math.radians(HOME_LAT))


class SimState:
    """Ground truth in local ENU metres relative to home."""

    def __init__(self) -> None:
        self.mode = "DISARMED"
        self.armed = False
        self.e = self.n = self.u = 0.0
        self.tgt_e: float | None = None
        self.tgt_n: float | None = None
        self.tgt_u = 0.0
        self.battery = 100.0
        self.heading = 0.0
        self.ve = self.vn = self.vu = 0.0
        self._t = time.monotonic()

        # real navigation filter
        self.filter = None
        self.nav_backend = NAV_BACKEND
        self.nis = 0.0
        if AdaptiveUKF is not None:
            try:
                self.filter = AdaptiveUKF()
                self.filter.initialize(0, 0, 0, 0, 0, 0)
            except Exception:
                self.filter, self.nav_backend = None, "raw-truth"
        else:
            self.nav_backend = "raw-truth"

        # real control law (LQR on 6-state ENU double integrator)
        self.lqr = None
        self.control_backend = "naive-mover"
        if LQRController is not None and np is not None:
            try:
                A = np.eye(6); A[:3, 3:] = np.eye(3) * FDT
                B = np.zeros((6, 3)); B[3:, :] = np.eye(3) * FDT
                Q = np.diag([8.0, 8.0, 8.0, 4.0, 4.0, 4.0])
                R = np.eye(3) * 0.5
                self.lqr = LQRController(A, B, Q, R)
                self._A, self._B = A, B
                self.control_backend = CTRL_BACKEND
            except Exception:
                self.lqr = None

        # real C-UAS detection + a SIMULATED intruder track
        self.clf = None
        self.detect_backend = "none"
        self.threats: list[dict] = []
        self.intr_e, self.intr_n, self.intr_u = 400.0, 0.0, 80.0
        if CUASClassifier is not None:
            try:
                self.clf = CUASClassifier(sensitivity=0.5)
                self.detect_backend = DETECT_BACKEND
            except Exception:
                self.clf = None

    # ---- commands (mirror GCS TelemetryService.sendCommand) ----
    def command(self, cmd: str, p: dict) -> None:
        airborne = self.u > 0.5 or self.mode in ("TAKEOFF", "FLYING", "RTL")
        if cmd == "arm" and not airborne:
            self.armed, self.mode = True, "ARMED"
        elif cmd == "disarm" and not airborne:
            self.armed, self.mode = False, "DISARMED"
        elif cmd == "takeoff":
            self.armed = True
            self.tgt_u = float(p.get("altitude", 30.0))
            self.mode = "TAKEOFF"
        elif cmd == "land":
            self.tgt_e = self.tgt_n = None
            self.tgt_u = 0.0
            self.mode = "LANDING"
        elif cmd == "rtl":
            self.tgt_e, self.tgt_n = 0.0, 0.0
            self.mode = "RTL"
        elif cmd == "goto" and airborne:
            self.tgt_e = (float(p["lon"]) - HOME_LON) * M_PER_DEG_LON
            self.tgt_n = (float(p["lat"]) - HOME_LAT) * M_PER_DEG_LAT
            self.tgt_u = float(p.get("altitude", self.u))
            self.mode = "FLYING"

    # ---- time evolution ----
    def step(self) -> None:
        now = time.monotonic()
        dt = now - self._t
        self._t = now
        if dt <= 0:
            return

        if self.armed and (self.u > 0.1 or self.mode in ("TAKEOFF", "FLYING", "RTL", "LANDING")):
            self.battery = max(0.0, self.battery - BATTERY_DRAIN * dt)
        if self.battery <= 0.0 and self.mode != "DISARMED":
            self.mode, self.tgt_e, self.tgt_n, self.tgt_u = "LANDING", None, None, 0.0

        if self.lqr is not None:
            try:
                self._lqr_step()
            except Exception:
                self.lqr, self.control_backend = None, "naive-mover (LQR diverged)"
                self._naive_step()
        else:
            self._naive_step()

        # mode transitions (read self.u + target distance)
        if self.mode == "TAKEOFF" and self.u >= self.tgt_u - 0.2:
            self.mode = "FLYING"
        elif self.mode == "RTL" and self.tgt_e is None and self.u > 0.5:
            self.tgt_u, self.mode = 0.0, "LANDING"
        elif self.mode == "LANDING" and self.u <= 0.15:
            self.u, self.armed, self.mode = 0.0, False, "DISARMED"

        self._detect_step()
        self._filter_step(dt)

    def _lqr_step(self) -> None:
        x = np.array([self.e, self.n, self.u, self.ve, self.vn, self.vu])
        des_e = self.tgt_e if self.tgt_e is not None else self.e
        des_n = self.tgt_n if self.tgt_n is not None else self.n
        x_des = np.array([des_e, des_n, self.tgt_u, 0.0, 0.0, 0.0])
        if self.u <= 0.5:                       # no horizontal command until airborne
            x_des[0], x_des[1] = self.e, self.n
        u = np.clip(self.lqr.compute(x, x_des), -ACCEL_CLIP, ACCEL_CLIP)
        xn = self._A @ x + self._B @ u
        if not np.all(np.isfinite(xn)):
            raise ValueError("non-finite")
        # drone-like velocity envelope
        vh = math.hypot(xn[3], xn[4])
        if vh > MAX_H_SPEED:
            xn[3] *= MAX_H_SPEED / vh
            xn[4] *= MAX_H_SPEED / vh
        xn[5] = max(-MAX_V_SPEED, min(MAX_V_SPEED, xn[5]))
        self.e, self.n = float(xn[0]), float(xn[1])
        self.u = max(0.0, float(xn[2]))
        self.ve, self.vn, self.vu = float(xn[3]), float(xn[4]), float(xn[5])
        if math.hypot(self.ve, self.vn) > 0.1:
            self.heading = (math.degrees(math.atan2(self.ve, self.vn)) + 360) % 360
        if self.tgt_e is not None and math.hypot(self.tgt_e - self.e, self.tgt_n - self.n) < 0.6:
            self.tgt_e = self.tgt_n = None       # reached waypoint -> hold

    def _naive_step(self) -> None:
        dt = FDT
        self.vu = 0.0
        if abs(self.u - self.tgt_u) > 0.05:
            d = math.copysign(min(CLIMB_RATE * dt, abs(self.tgt_u - self.u)), self.tgt_u - self.u)
            self.u += d
            self.vu = d / dt
        else:
            self.u = self.tgt_u
        self.ve = self.vn = 0.0
        if self.tgt_e is not None and self.tgt_n is not None and self.u > 0.5:
            de, dn = self.tgt_e - self.e, self.tgt_n - self.n
            dist = math.hypot(de, dn)
            if dist > 1.0:
                move = min(CRUISE_SPEED * dt, dist)
                self.ve, self.vn = de / dist * move / dt, dn / dist * move / dt
                self.e += self.ve * dt
                self.n += self.vn * dt
                self.heading = (math.degrees(math.atan2(de, dn)) + 360) % 360
            else:
                self.e, self.n, self.tgt_e, self.tgt_n = self.tgt_e, self.tgt_n, None, None

    def _detect_step(self) -> None:
        if self.clf is None or ThreatFeatures is None:
            return
        # advance the SIMULATED intruder: closes on home from the east, descending
        self.intr_e -= INTRUDER_SPEED * FDT
        dist_home = math.hypot(self.intr_e, self.intr_n)
        self.intr_u = 30.0 + min(1.0, dist_home / 400.0) * 50.0   # 80 m far -> 30 m near
        if self.intr_e < -60.0:                                    # passed us -> respawn
            self.intr_e = 400.0
        try:
            # threat geometry is relative to the defended point (home = 0,0,0)
            dist = math.sqrt(self.intr_e ** 2 + self.intr_n ** 2 + self.intr_u ** 2)
            bearing = (math.degrees(math.atan2(self.intr_e, self.intr_n)) + 360) % 360
            feat = ThreatFeatures(
                radar_cross_section_db=-18.0, ground_speed_m_s=INTRUDER_SPEED,
                altitude_m=self.intr_u, vertical_speed_m_s=0.0, size_m=0.8,
                signal_strength_db=-70.0, track_direction_deg=bearing,
                jammer_present=False, last_seen_sec=time.time(),
            )
            r = self.clf.classify(feat)
            sev = {0: "low", 1: "low", 2: "medium", 3: "high", 4: "critical"}[r.threat_level.value]
            self.threats = [{
                "id": "intruder-1",
                "type": r.category.value,
                "severity": sev,
                "distance": round(dist, 1),
                "bearing": round(bearing, 1),
                "confidence": round(r.confidence, 2),
                "timestamp": round(r.timestamp * 1000.0),   # ms, for JS new Date()
            }]
        except Exception:
            self.threats, self.detect_backend = [], "none (classify failed)"

    def _filter_step(self, dt: float) -> None:
        if self.filter is None or np is None:
            return
        try:
            self.filter.predict(np.array([0.0, 0.0, -9.81]), np.zeros(3), dt)
            gps = {
                "lat": self.n + random.gauss(0, GPS_NOISE_H),
                "lon": self.e + random.gauss(0, GPS_NOISE_H),
                "alt": self.u + random.gauss(0, GPS_NOISE_V),
                "vx": self.vn, "vy": self.ve, "vz": self.vu,
            }
            _, nis = self.filter.update(gps, self.u)
            self.nis = float(nis)
            if not np.all(np.isfinite(self.filter.x)):
                raise ValueError("non-finite state")
        except Exception:
            self.filter, self.nav_backend = None, "raw-truth (AUKF diverged)"

    def _estimate_enu(self):
        if self.filter is not None:
            n, e, u = self.filter.get_position_llh()
            vn, ve, vu = self.filter.get_velocity_ned()
            return n, e, u, math.sqrt(vn * vn + ve * ve + vu * vu)
        return self.n, self.e, self.u, math.hypot(math.hypot(self.ve, self.vn), self.vu)

    def snapshot(self) -> dict:
        n, e, u, speed = self._estimate_enu()
        return {
            "source": "simulator",
            "nav_backend": self.nav_backend,
            "control_backend": self.control_backend,
            "detect_backend": self.detect_backend,
            "nav_nis": round(self.nis, 2),
            "mode": self.mode,
            "armed": self.armed,
            "battery": {"percent": round(self.battery, 1)},
            "position": {
                "lat": round(HOME_LAT + n / M_PER_DEG_LAT, 6),
                "lon": round(HOME_LON + e / M_PER_DEG_LON, 6),
                "altitude": round(max(0.0, u), 1),
            },
            "velocity": {"speed": round(speed if self.u > 0.5 else 0.0, 1)},
            "attitude": {"yaw": round(self.heading, 1)},
        }

    def threat_feed(self) -> dict:
        return {"source": "simulator", "detect_backend": self.detect_backend, "threats": self.threats}


state = SimState()
app = FastAPI(title="SkyCore Live Backend (real AUKF + LQR + C-UAS)", version="3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def _start() -> None:
    async def loop() -> None:
        while True:
            state.step()
            await asyncio.sleep(1.0 / TICK_HZ)
    asyncio.create_task(loop())


@app.get("/")
async def root() -> dict:
    return {
        "service": "SkyCore Live Backend", "status": "running",
        "nav_backend": state.nav_backend, "control_backend": state.control_backend,
        "detect_backend": state.detect_backend,
    }


@app.get("/telemetry")
async def telemetry() -> dict:
    return state.snapshot()


@app.get("/threats")
async def threats() -> dict:
    return state.threat_feed()


@app.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket) -> None:
    await ws.accept()

    async def receiver() -> None:
        try:
            while True:
                msg = await ws.receive_json()
                cmd = msg.get("command")
                if cmd:
                    state.command(cmd, {k: v for k, v in msg.items() if k != "command"})
                    print(f"[cmd] {cmd} -> mode={state.mode}", flush=True)
        except Exception:
            return

    recv = asyncio.create_task(receiver())
    try:
        while True:
            await ws.send_json(state.snapshot())
            await asyncio.sleep(0.2)
    except Exception:
        pass
    finally:
        recv.cancel()


@app.websocket("/ws/threats")
async def ws_threats(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            await ws.send_json(state.threat_feed())
            await asyncio.sleep(0.5)
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    print(f"SkyCore live backend :8080 | nav={state.nav_backend} | ctrl={state.control_backend} | detect={state.detect_backend}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
