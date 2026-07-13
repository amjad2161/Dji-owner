"""
SkyCore live backend.

Serves telemetry + accepts flight commands over WebSocket in the exact shape the
SkyCore GCS expects (ws://<host>:8080/ws/telemetry).

HONEST design:
  - A physics-lite SIMULATOR generates ground truth (battery drain, climb, motion
    toward waypoints) over real time.
  - Noisy "GPS" measurements are fed to the REAL skycore 22-state Adaptive UKF
    (skycore/navigation/aukf.py). The telemetry the GCS shows is the FILTER'S
    estimate, not the raw truth. So the live demo runs on the genuine navigation
    algorithm.
  - Every frame is tagged source="simulator" and reports which nav backend is
    active. No physical drone is claimed. If the real AUKF can't be imported or
    goes non-finite, we fall back to raw truth and say so (backend="raw-truth").

Run:  python serve.py
Deps: fastapi, uvicorn[standard], numpy
Env:  SKYCORE_NAV=<path to skycore/navigation> to override AUKF discovery.
"""
from __future__ import annotations

import asyncio
import math
import os
import random
import sys
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# --- locate + import the REAL 22-state AUKF (honest provenance, like reference/sky.py) ---
_here = os.path.dirname(os.path.abspath(__file__))
_NAV_CANDIDATES = [
    os.environ.get("SKYCORE_NAV", ""),
    os.path.join(_here, "..", "..", "src", "skycore_v1.0.0", "skycore", "navigation"),
    os.path.join(_here, "..", "src", "skycore_v1.0.0", "skycore", "navigation"),
    r"C:\Users\Mobar\OneDrive\Desktop\SkyCore_Consolidated\src\skycore_v1.0.0\skycore\navigation",
]
AdaptiveUKF = None
NAV_BACKEND = "raw-truth"
for _cand in _NAV_CANDIDATES:
    if _cand and os.path.isfile(os.path.join(_cand, "aukf.py")):
        sys.path.insert(0, _cand)
        try:
            from aukf import AdaptiveUKF  # type: ignore
            NAV_BACKEND = "skycore.navigation.aukf.AdaptiveUKF (22-state)"
            break
        except Exception:
            AdaptiveUKF = None

try:
    import numpy as np
except Exception:
    np = None
    AdaptiveUKF = None
    NAV_BACKEND = "raw-truth"

HOME_LAT, HOME_LON = 32.0853, 34.7818
CLIMB_RATE = 2.5
CRUISE_SPEED = 9.0
BATTERY_DRAIN = 0.06
TICK_HZ = 10.0
GPS_NOISE_H = 1.2   # metres, horizontal 1-sigma
GPS_NOISE_V = 0.6   # metres, vertical
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LON = M_PER_DEG_LAT * math.cos(math.radians(HOME_LAT))


class SimState:
    """Ground truth in local ENU metres relative to home."""

    def __init__(self) -> None:
        self.mode = "DISARMED"
        self.armed = False
        self.e = 0.0   # east  (m)
        self.n = 0.0   # north (m)
        self.u = 0.0   # up    (m)
        self.tgt_e: float | None = None
        self.tgt_n: float | None = None
        self.tgt_u = 0.0
        self.battery = 100.0
        self.heading = 0.0
        self.ve = self.vn = self.vu = 0.0
        self._t = time.monotonic()

        # real filter
        self.filter = None
        self.backend = NAV_BACKEND
        self.nis = 0.0
        if AdaptiveUKF is not None:
            try:
                self.filter = AdaptiveUKF()
                self.filter.initialize(0, 0, 0, 0, 0, 0)
            except Exception:
                self.filter, self.backend = None, "raw-truth"

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

    # ---- time evolution (ground truth) ----
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

        # vertical
        self.vu = 0.0
        if abs(self.u - self.tgt_u) > 0.05:
            d = math.copysign(min(CLIMB_RATE * dt, abs(self.tgt_u - self.u)), self.tgt_u - self.u)
            self.u += d
            self.vu = d / dt
        else:
            self.u = self.tgt_u

        # horizontal
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

        # mode transitions
        if self.mode == "TAKEOFF" and self.u >= self.tgt_u - 0.1:
            self.mode = "FLYING"
        elif self.mode == "RTL" and self.tgt_e is None and self.u > 0.5:
            self.tgt_u, self.mode = 0.0, "LANDING"
        elif self.mode == "LANDING" and self.u <= 0.1:
            self.u, self.armed, self.mode = 0.0, False, "DISARMED"

        self._filter_step(dt)

    def _filter_step(self, dt: float) -> None:
        """Feed noisy measurements of ground truth into the real AUKF."""
        if self.filter is None or np is None:
            return
        try:
            self.filter.predict(np.array([0.0, 0.0, -9.81]), np.zeros(3), dt)
            gps = {
                "lat": self.n + random.gauss(0, GPS_NOISE_H),   # north
                "lon": self.e + random.gauss(0, GPS_NOISE_H),   # east
                "alt": self.u + random.gauss(0, GPS_NOISE_V),
                "vx": self.vn, "vy": self.ve, "vz": self.vu,
            }
            _, nis = self.filter.update(gps, self.u)
            self.nis = float(nis)
            if not np.all(np.isfinite(self.filter.x)):
                raise ValueError("non-finite state")
        except Exception:
            # honest fallback: drop to raw truth, stop pretending the filter is live
            self.filter, self.backend = None, "raw-truth (AUKF diverged)"

    def _estimate_enu(self) -> tuple[float, float, float, float]:
        """Return (north, east, up, speed) — filtered if AUKF live, else raw truth."""
        if self.filter is not None:
            n, e, u = self.filter.get_position_llh()
            vn, ve, vu = self.filter.get_velocity_ned()
            return n, e, u, math.sqrt(vn * vn + ve * ve + vu * vu)
        return self.n, self.e, self.u, math.hypot(math.hypot(self.ve, self.vn), self.vu)

    def snapshot(self) -> dict:
        n, e, u, speed = self._estimate_enu()
        return {
            "source": "simulator",
            "nav_backend": self.backend,
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


state = SimState()
app = FastAPI(title="SkyCore Live Backend (real AUKF)", version="2.0")
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
    return {"service": "SkyCore Live Backend", "status": "running", "nav_backend": state.backend}


@app.get("/telemetry")
async def telemetry() -> dict:
    return state.snapshot()


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


if __name__ == "__main__":
    import uvicorn
    print(f"SkyCore live backend on http://0.0.0.0:8080  | nav backend: {state.backend}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
