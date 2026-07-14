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
import base64
import hashlib
import hmac
import json
import logging
import math
import os
import random
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=os.environ.get("SKYCORE_LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("skycore")

try:
    import numpy as np
except Exception:
    np = None

# --- locate the real skycore package and import its modules directly (avoids
#     package __init__ side effects), mirroring the honest provenance pattern. ---
_here = os.path.dirname(os.path.abspath(__file__))
_PKG_CANDIDATES = [
    os.environ.get("SKYCORE_PKG", ""),
    os.path.join(_here, "skycore"),                                   # vendored (self-contained / Docker)
    os.path.join(_here, "..", "..", "src", "skycore_v1.0.0", "skycore"),
    os.path.join(_here, "..", "src", "skycore_v1.0.0", "skycore"),
    r"C:\Users\Mobar\OneDrive\Desktop\SkyCore_Consolidated\src\skycore_v1.0.0\skycore",
]
AdaptiveUKF = LQRController = CUASClassifier = ThreatFeatures = GeofenceValidator = GeofenceConfig = RRTStarPlanner = preflight_check = FlightDatabase = None
NAV_BACKEND = CTRL_BACKEND = DETECT_BACKEND = GEOFENCE_BACKEND = WEATHER_BACKEND = "unavailable"
if np is not None:
    for _pkg in _PKG_CANDIDATES:
        if _pkg and os.path.isdir(_pkg):
            sys.path.insert(0, _pkg)                         # for root modules (openmeteo)
            for _sub in ("navigation", "control", "cuas", "storage"):
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
            try:
                from geofence import GeofenceValidator, GeofenceConfig  # type: ignore
                GEOFENCE_BACKEND = "skycore.navigation.geofence.GeofenceValidator (circular)"
            except Exception:
                GeofenceValidator = GeofenceConfig = None
            try:
                from rrt import RRTStarPlanner  # type: ignore
            except Exception:
                RRTStarPlanner = None
            try:
                from openmeteo import preflight_check  # type: ignore
                WEATHER_BACKEND = "skycore.openmeteo (Open-Meteo, live)"
            except Exception:
                preflight_check = None
            try:
                from flight_db import FlightDatabase  # type: ignore
            except Exception:
                FlightDatabase = None
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
NOFLY_E, NOFLY_N, NOFLY_R = 150.0, 80.0, 60.0   # one circular no-fly zone, ENU metres
_weather = {"backend": WEATHER_BACKEND, "ok": None, "issues": ["fetching…"],
            "temp_c": None, "wind_kph": None, "gust_kph": None, "precip_mm_h": None,
            "clouds_pct": None, "fetched_at": None}


# ----------------------------------------------------------------------------
# Config (env-driven) + authentication. This is legitimate access control for a
# command/telemetry surface: without it any client that can reach the port could
# arm/fly the (simulated) aircraft and read all data. Defaults: bind to loopback,
# require a signed token on every data API and WebSocket. Set SKYCORE_HOST=0.0.0.0
# (and provide SKYCORE_JWT_SECRET + real users) to expose beyond localhost.
# ----------------------------------------------------------------------------
HOST = os.environ.get("SKYCORE_HOST", "127.0.0.1")
PORT = int(os.environ.get("SKYCORE_PORT", "8080"))
AUTH_ENABLED = os.environ.get("SKYCORE_AUTH", "on").strip().lower() not in ("off", "0", "false", "no")
TOKEN_TTL = int(os.environ.get("SKYCORE_TOKEN_TTL", str(12 * 3600)))
JWT_SECRET = os.environ.get("SKYCORE_JWT_SECRET") or base64.urlsafe_b64encode(os.urandom(32)).decode()
CORS_ORIGINS = [o.strip() for o in os.environ.get("SKYCORE_CORS_ORIGINS", "").split(",") if o.strip()] or [
    "http://localhost:4173", "http://127.0.0.1:4173",   # vite preview (dev)
    "http://localhost:5173", "http://127.0.0.1:5173",   # vite dev server
]


def _hash_pw(pw: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 120_000)


# Users are defined + verified SERVER-SIDE (the client ships no credential map).
# Override with SKYCORE_USERS='{"user":{"password":"..","role":".."}}'.
_DEMO_USERS = {"admin": ("admin123", "operator"), "operator": ("operator123", "operator"),
               "viewer": ("viewer123", "viewer"), "demo": ("demo", "viewer")}
try:
    _raw_users = json.loads(os.environ.get("SKYCORE_USERS", "") or "{}")
    if _raw_users:
        _DEMO_USERS = {u: (v.get("password", ""), v.get("role", "viewer")) for u, v in _raw_users.items()}
except Exception:
    pass
_USERS: dict = {}
for _u, (_pw, _role) in _DEMO_USERS.items():
    _salt = os.urandom(16)
    _USERS[_u] = {"hash": _hash_pw(_pw, _salt), "salt": _salt, "role": _role}


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(sub: str, role: str) -> str:
    """Mint a signed (HMAC-SHA256) JWT-shaped token with an expiry."""
    header = _b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64u(json.dumps({"sub": sub, "role": role, "exp": int(time.time()) + TOKEN_TTL},
                               separators=(",", ":")).encode())
    body = f"{header}.{payload}"
    sig = _b64u(hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: str):
    """Return the token payload if the signature is valid and it has not expired, else None."""
    try:
        header, payload, sig = token.split(".")
        body = f"{header}.{payload}"
        expected = _b64u(hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_b64u_dec(payload))
        if int(data.get("exp", 0)) < time.time():
            return None
        return data
    except Exception:
        return None


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
        # three SIMULATED intruder tracks with distinct behaviours (each fed to the REAL classifier)
        self.intruders = [
            {"id": "trk-approach",  "beh": "approach",  "e": 400.0, "n": 0.0,    "u": 80.0, "th": 0.0, "prev": 400.0, "hist": []},
            {"id": "trk-loiter",    "beh": "loiter",    "e": 295.0, "n": -150.0, "u": 60.0, "th": 0.0, "prev": 331.0, "hist": []},
            {"id": "trk-incursion", "beh": "incursion", "e": 150.0, "n": -250.0, "u": 45.0, "th": 0.0, "prev": 291.0, "hist": []},
        ]
        if CUASClassifier is not None:
            try:
                self.clf = CUASClassifier(sensitivity=0.5)
                self.detect_backend = DETECT_BACKEND
            except Exception:
                self.clf = None

        # real geofence — one circular no-fly zone (module is circle-based, not polygon)
        self.gf = None
        self.geofence_backend = "none"
        self.geofence_reason = ""
        self._gf_ticks = 0
        if GeofenceValidator is not None:
            try:
                self.gf = GeofenceValidator(GeofenceConfig(
                    max_altitude=120.0, max_distance=100000.0, home=(HOME_LAT, HOME_LON, 0.0)))
                nf_lat = HOME_LAT + NOFLY_N / M_PER_DEG_LAT
                nf_lon = HOME_LON + NOFLY_E / M_PER_DEG_LON
                # full-altitude no-fly cylinder (module now treats inside-radius as the breach)
                self.gf.add_circular_zone(nf_lat, nf_lon, 0.0, radius_m=NOFLY_R, name="nofly-1")
                self.geofence_backend = GEOFENCE_BACKEND
            except Exception:
                self.gf, self.geofence_backend = None, "none (geofence init failed)"

        # real path planner (RRT*) — route around the no-fly zone
        self.last_tick_mono = time.monotonic()   # updated each sim tick; /api/readyz reads its age
        self.rrt = None
        self._rrt_lock = threading.Lock()   # serialize solves: plan() mutates shared planner state
        self.route_backend = "none"
        self.wp_queue: list = []
        self.route: list = []
        if RRTStarPlanner is not None:
            try:
                self.rrt = RRTStarPlanner((-400.0, 400.0, -400.0, 400.0, 0.0, 120.0), max_altitude=120)
                self.rrt.max_nodes = 1200        # bound planning time (default 5000 is slow)
                self.rrt.step_size = 12.0
                self.rrt.rewire_radius = 24.0
                self.rrt.goal_bias = 0.2
                self.route_backend = "skycore.navigation.rrt.RRTStarPlanner"
            except Exception:
                self.rrt = None

        # flight history (real SQLite)
        self.db = None
        self._fl_active = False
        self._fl = {"start": "", "max_alt": 0.0, "dist_m": 0.0, "batt0": 100.0}
        if FlightDatabase is not None:
            try:
                self.db = FlightDatabase(os.environ.get("SKYCORE_DB", os.path.join(_here, "flights.db")))
            except Exception:
                self.db = None

    @staticmethod
    def _seg_crosses_zone(e0: float, n0: float, e1: float, n1: float) -> bool:
        dx, dy = e1 - e0, n1 - n0
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 < 1e-6 else max(0.0, min(1.0, ((NOFLY_E - e0) * dx + (NOFLY_N - n0) * dy) / l2))
        cx, cy = e0 + t * dx, n0 + t * dy
        return math.hypot(NOFLY_E - cx, NOFLY_N - cy) < NOFLY_R

    # ---- commands (mirror GCS TelemetryService.sendCommand) ----
    def command(self, cmd: str, p: dict, plan_inline: bool = True) -> None:
        airborne = self.u > 0.5 or self.mode in ("TAKEOFF", "FLYING", "RTL")
        if cmd in ("takeoff", "land", "rtl", "goto"):
            self.wp_queue, self.route = [], []   # a new target cancels any active route
            self._pending_route = None
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
            try:
                lat, lon = float(p["lat"]), float(p["lon"])
            except (KeyError, TypeError, ValueError):
                return                                    # ignore a malformed goto, keep the socket alive
            alt = float(p.get("altitude", self.u))
            if self.gf is not None:                       # reject a waypoint inside the no-fly zone
                try:
                    ok, reason = self.gf.is_safe_to_fly(lat, lon, alt)
                except Exception:
                    ok, reason = True, ""
                if not ok:
                    self.geofence_reason = f"goto blocked: {reason}"
                    return
            self.geofence_reason = ""
            te = (lon - HOME_LON) * M_PER_DEG_LON
            tn = (lat - HOME_LAT) * M_PER_DEG_LAT
            self.tgt_u = alt
            self.route = []
            self.wp_queue = []
            # if the straight path would cross the no-fly zone, plan a route AROUND it (real RRT*)
            if self.rrt is not None and self._seg_crosses_zone(self.e, self.n, te, tn):
                if not plan_inline:
                    # defer the CPU-bound RRT* solve so the async caller runs it OFF the
                    # event loop (asyncio.to_thread) instead of blocking telemetry frames
                    self._pending_route = (self.e, self.n, self.u, te, tn, alt)
                    return
                path = self._solve_route((self.e, self.n, self.u), te, tn, alt)
                self.apply_route(path, te, tn, alt)
                return
            self.tgt_e, self.tgt_n, self.mode = te, tn, "FLYING"

    def _solve_route(self, start: tuple, te: float, tn: float, alt: float):
        """Real RRT* solve around the no-fly zone, run in a worker thread via
        asyncio.to_thread. plan() mutates the shared planner's nodes/obstacles/
        start/goal, so concurrent gotos from two clients would corrupt each other —
        the lock serializes solves (does not touch other SimState fields)."""
        with self._rrt_lock:
            try:
                self.rrt.clear_obstacles()
                self.rrt.add_obstacle(NOFLY_E, NOFLY_N, alt, NOFLY_R + 30.0)  # margin > LQR turn overshoot
                return self.rrt.plan(start, (te, tn, alt))
            except Exception:
                return None

    def apply_route(self, path, te: float, tn: float, alt: float) -> None:
        self._pending_route = None
        if path and len(path) >= 2:
            self.route = [{"e": round(float(wp[0]), 1), "n": round(float(wp[1]), 1)} for wp in path]
            self.wp_queue = [(float(wp[0]), float(wp[1]), alt) for wp in path[1:]]
            first = self.wp_queue.pop(0)
            self.tgt_e, self.tgt_n, self.mode = first[0], first[1], "FLYING"
            return
        # avoidance was required but RRT* found no valid route: REJECT the goto rather than
        # fly the straight line that is KNOWN to cross the no-fly zone (would trip RTL).
        self.geofence_reason = "goto blocked: no clear route around no-fly zone"

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
            self.wp_queue, self.route = [], []

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
        self._geofence_step()
        self._flight_step()
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
        if self.tgt_e is not None and math.hypot(self.tgt_e - self.e, self.tgt_n - self.n) < 3.0:
            if self.wp_queue:                    # advance to the next planned RRT* waypoint
                nxt = self.wp_queue.pop(0)
                self.tgt_e, self.tgt_n, self.tgt_u = nxt[0], nxt[1], nxt[2]
            else:
                self.tgt_e = self.tgt_n = None   # arrived -> hold
                self.route = []

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
                self.e, self.n = self.tgt_e, self.tgt_n
                if self.wp_queue:                    # advance along the RRT* route (mirror _lqr_step)
                    nxt = self.wp_queue.pop(0)
                    self.tgt_e, self.tgt_n, self.tgt_u = nxt[0], nxt[1], nxt[2]
                else:
                    self.tgt_e = self.tgt_n = None
                    self.route = []

    def _detect_step(self) -> None:
        if self.clf is None or ThreatFeatures is None:
            return
        threats = []
        for it in self.intruders:
            if it["beh"] == "approach":                     # fast straight run at home, descending
                it["e"] -= 18.0 * FDT
                it["u"] = 30.0 + min(1.0, math.hypot(it["e"], it["n"]) / 400.0) * 50.0
                if it["e"] < -60.0:
                    it["e"], it["hist"] = 400.0, []
                speed = 18.0
            elif it["beh"] == "loiter":                     # tight circle -> stays in a bounded region
                it["th"] = (it["th"] + (8.0 / 25.0) * FDT) % (2 * math.pi)
                it["e"] = 250.0 + 25.0 * math.cos(it["th"])
                it["n"] = -150.0 + 25.0 * math.sin(it["th"])
                speed = 8.0
            else:                                           # incursion: drives north into the no-fly zone
                it["n"] += 10.0 * FDT
                if it["n"] > 120.0:
                    it["n"], it["hist"] = -250.0, []
                speed = 10.0
            try:
                dist = math.sqrt(it["e"] ** 2 + it["n"] ** 2 + it["u"] ** 2)
                bearing = (math.degrees(math.atan2(it["e"], it["n"])) + 360) % 360
                feat = ThreatFeatures(
                    radar_cross_section_db=-18.0, ground_speed_m_s=speed, altitude_m=it["u"],
                    vertical_speed_m_s=0.0, size_m=0.8, signal_strength_db=-70.0,
                    track_direction_deg=bearing, jammer_present=False, last_seen_sec=time.time(),
                )
                r = self.clf.classify(feat)                 # REAL classifier -> category + severity
                sev = {0: "low", 1: "low", 2: "medium", 3: "high", 4: "critical"}[r.threat_level.value]
                it["hist"].append((it["e"], it["n"]))
                if len(it["hist"]) > 100:
                    it["hist"].pop(0)
                behavior = self._behavior(it, dist)          # honest kinematic behaviour label
                it["prev"] = dist
                threats.append({
                    "id": it["id"], "type": r.category.value, "severity": sev, "behavior": behavior,
                    "distance": round(dist, 1), "bearing": round(bearing, 1),
                    "confidence": round(r.confidence, 2), "timestamp": round(r.timestamp * 1000.0),
                })
            except Exception:
                continue
        rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        self.threats = sorted(threats, key=lambda t: rank.get(t["severity"], 9))

    def _behavior(self, it: dict, dist_home: float) -> str:
        """Behaviour from the track's own kinematics (not from the classifier)."""
        if math.hypot(it["e"] - NOFLY_E, it["n"] - NOFLY_N) < NOFLY_R + 40.0:
            return "restricted_zone"
        if (it["prev"] - dist_home) / FDT > 10.0:            # closing on home fast
            return "fast_approach"
        h = it["hist"]
        if len(h) >= 60:                                    # stays in a bounded region while moving
            cx = sum(p[0] for p in h) / len(h)
            cy = sum(p[1] for p in h) / len(h)
            maxr = max(math.hypot(p[0] - cx, p[1] - cy) for p in h)
            path = sum(math.hypot(h[i + 1][0] - h[i][0], h[i + 1][1] - h[i][1]) for i in range(len(h) - 1))
            if maxr < 40.0 and path > 40.0:
                return "loitering"
        return "transit"

    def _geofence_step(self) -> None:
        """Per-tick geofence check (real GeofenceValidator, lat/lon degrees); RTL on breach."""
        if self.gf is None:
            return
        self._gf_ticks += 1
        if self._gf_ticks % 600 == 0:          # bound the validator's violation history
            try:
                self.gf.reset()
            except Exception:
                pass
        if self.u <= 0.5:
            return
        try:
            lat = HOME_LAT + self.n / M_PER_DEG_LAT
            lon = HOME_LON + self.e / M_PER_DEG_LON
            ok, reason = self.gf.is_safe_to_fly(lat, lon, self.u)
        except Exception:
            return
        if not ok and self.mode not in ("RTL", "LANDING"):
            self.geofence_reason = f"geofence breach -> RTL: {reason}"
            self.tgt_e, self.tgt_n = 0.0, 0.0
            self.wp_queue, self.route = [], []
            self.mode = "RTL"

    def _flight_step(self) -> None:
        """Log each flight (takeoff -> land) to the real SQLite store."""
        if self.db is None:
            return
        flying = self.armed and (self.u > 0.5 or self.mode in ("TAKEOFF", "FLYING", "RTL", "LANDING"))
        if flying and not self._fl_active:
            self._fl_active = True
            self._fl = {"start": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "max_alt": self.u, "dist_m": 0.0, "batt0": self.battery}
        elif self._fl_active:
            self._fl["max_alt"] = max(self._fl["max_alt"], self.u)
            self._fl["dist_m"] += math.hypot(self.ve, self.vn) * FDT
            if self.mode == "DISARMED":
                try:
                    self.db.log_flight(
                        "SIM-1", self._fl["start"],
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        round(self._fl["max_alt"], 1), round(self._fl["dist_m"] / 1000.0, 3),
                        round(self._fl["batt0"] - self.battery, 1),
                    )
                except Exception as ex:
                    log.warning("flight-log write failed (flight dropped): %s", ex)
                self._fl_active = False

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
            "geofence": {"backend": self.geofence_backend, "reason": self.geofence_reason},
            "planner": {"backend": self.route_backend, "waypoints": len(self.wp_queue)},
            "route": self.route,
        }

    def threat_feed(self) -> dict:
        return {"source": "simulator", "detect_backend": self.detect_backend, "threats": self.threats}


state = SimState()


async def _sim_loop() -> None:
    while True:
        try:
            state.step()
            state.last_tick_mono = time.monotonic()
        except Exception as ex:                 # never let one bad tick freeze telemetry silently
            log.exception("sim step failed: %s", ex)
        await asyncio.sleep(1.0 / TICK_HZ)


async def _weather_loop() -> None:
    while True:
        delay = 300                             # Open-Meteo refresh interval
        if preflight_check is not None:
            try:
                ok, issues, snap = await asyncio.to_thread(preflight_check, HOME_LAT, HOME_LON)
                _weather.update({
                    "backend": WEATHER_BACKEND, "ok": ok, "issues": issues,
                    "temp_c": round(snap.temperature_c, 1), "wind_kph": round(snap.wind_speed_kph, 1),
                    "gust_kph": round(snap.wind_gust_kph, 1), "precip_mm_h": round(snap.precipitation_mm_h, 2),
                    "clouds_pct": round(snap.cloud_cover_pct), "fetched_at": time.monotonic(),
                })
            except Exception as ex:
                log.warning("weather fetch failed: %s", ex)
                _weather["issues"] = ["weather fetch failed"]
                delay = 30                       # retry sooner instead of holding stale data for 5 min
        else:
            _weather["backend"], _weather["issues"] = "unavailable", ["weather module not loaded"]
        await asyncio.sleep(delay)


@asynccontextmanager
async def _lifespan(_app: "FastAPI"):
    tasks = [asyncio.create_task(_sim_loop()), asyncio.create_task(_weather_loop())]
    log.info("SkyCore backend %s:%s | auth=%s | nav=%s | ctrl=%s | detect=%s",
             HOST, PORT, "on" if AUTH_ENABLED else "OFF",
             state.nav_backend, state.control_backend, state.detect_backend)
    try:
        yield
    finally:                                    # graceful shutdown: cancel tasks + close the DB
        for t in tasks:
            t.cancel()
        if state.db is not None:
            state.db.close()
        log.info("SkyCore backend shut down (tasks cancelled, DB closed)")


app = FastAPI(title="SkyCore Live Backend (real AUKF + LQR + C-UAS)", version="3.0", lifespan=_lifespan)
# Explicit origin allowlist (not "*"): same-origin under the unified server needs no
# CORS; this covers the dev cross-origin case (GCS :4173 -> backend :8080).
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,
                   allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])


def require_auth(authorization: str = Header(default="")):
    """FastAPI dependency: require a valid bearer token on protected routes."""
    if not AUTH_ENABLED:
        return {"sub": "anon", "role": "operator"}
    if authorization.startswith("Bearer "):
        data = verify_token(authorization[7:])
        if data:
            return data
    raise HTTPException(status_code=401, detail="unauthorized")


async def _ws_authorized(ws: WebSocket) -> bool:
    """Gate a WebSocket: Origin allowlist (browsers) + a valid token (query param,
    since browsers cannot set WS request headers). Non-browser clients send no
    Origin but still need a token."""
    origin = ws.headers.get("origin")
    if origin:
        same_origin = urlparse(origin).netloc == ws.headers.get("host", "")
        if not (same_origin or origin in CORS_ORIGINS):
            return False
    if not AUTH_ENABLED:
        return True
    return verify_token(ws.query_params.get("token", "")) is not None


@app.post("/api/login")
async def api_login(creds: dict) -> dict:
    """Verify credentials SERVER-SIDE and issue a signed token."""
    u, pw = str(creds.get("username", "")), str(creds.get("password", ""))
    rec = _USERS.get(u)
    if rec and hmac.compare_digest(_hash_pw(pw, rec["salt"]), rec["hash"]):
        return {"token": make_token(u, rec["role"]), "username": u, "role": rec["role"], "auth": AUTH_ENABLED}
    raise HTTPException(status_code=401, detail="invalid credentials")


@app.get("/api/healthz")
async def api_healthz() -> dict:
    """Public liveness endpoint (no auth) for health checks."""
    return {"status": "ok", "auth": AUTH_ENABLED}


@app.post("/api/chat", dependencies=[Depends(require_auth)])
async def api_chat(req: dict) -> dict:
    """Proxy the operator chat to OpenRouter so the API key stays SERVER-SIDE
    (env OPENROUTER_API_KEY) instead of being shipped in the browser bundle.
    Stays inert (honest offline reply) when no key is configured."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return {"ok": False, "reply": None, "reason": "no OPENROUTER_API_KEY configured on the server"}
    try:
        import urllib.request
        body = json.dumps({"model": req.get("model", "openai/gpt-4o-mini"),
                           "messages": req.get("messages", [])}).encode()
        rq = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
                                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        raw = await asyncio.to_thread(lambda: urllib.request.urlopen(rq, timeout=30).read())
        reply = json.loads(raw).get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"ok": True, "reply": reply}
    except Exception as ex:
        return {"ok": False, "reply": None, "reason": f"chat proxy error: {ex}"}


@app.get("/api/readyz")
async def api_readyz() -> JSONResponse:
    """Public readiness probe: reports 503 if the sim loop has stalled (a hung tick
    would otherwise leave /api/healthz + /api/status reporting 'running' forever)."""
    age = time.monotonic() - getattr(state, "last_tick_mono", 0.0)
    ready = age < 2.0
    return JSONResponse(
        {"ready": ready, "last_tick_age_s": round(age, 2),
         "db": state.db is not None, "nav": state.nav_backend},
        status_code=200 if ready else 503,
    )


@app.get("/api/status", dependencies=[Depends(require_auth)])
async def api_status() -> dict:
    return {
        "service": "SkyCore Live Backend", "status": "running",
        "nav_backend": state.nav_backend, "control_backend": state.control_backend,
        "detect_backend": state.detect_backend,
    }


@app.get("/api/telemetry", dependencies=[Depends(require_auth)])
async def api_telemetry() -> dict:
    return state.snapshot()


@app.get("/api/threats", dependencies=[Depends(require_auth)])
async def api_threats() -> dict:
    return state.threat_feed()


@app.get("/api/geofence", dependencies=[Depends(require_auth)])
async def api_geofence() -> dict:
    if state.gf is None:
        return {"enabled": False, "backend": state.geofence_backend, "zones": []}
    pts = [{"e": round(NOFLY_E + NOFLY_R * math.cos(2 * math.pi * i / 48), 1),
            "n": round(NOFLY_N + NOFLY_R * math.sin(2 * math.pi * i / 48), 1)} for i in range(48)]
    return {"enabled": True, "backend": state.geofence_backend, "zones": [{
        "name": "nofly-1", "shape": "circle",
        "center": {"e": NOFLY_E, "n": NOFLY_N}, "radius": NOFLY_R,
        "polygon_enu": pts,
        "center_latlon": {"lat": round(HOME_LAT + NOFLY_N / M_PER_DEG_LAT, 6),
                          "lon": round(HOME_LON + NOFLY_E / M_PER_DEG_LON, 6)}}]}


@app.get("/api/weather", dependencies=[Depends(require_auth)])
async def api_weather() -> dict:
    w = dict(_weather)
    fetched = w.pop("fetched_at", None)
    if fetched is not None:
        age = time.monotonic() - fetched
        w["age_s"] = round(age, 1)
        if age > 1800:          # don't present >30-min-old data as a current go/no-go verdict
            w["ok"], w["issues"] = None, list(w.get("issues", [])) + ["weather data stale"]
    return w


@app.get("/api/flights", dependencies=[Depends(require_auth)])
async def api_flights() -> dict:
    if state.db is None:
        return {"available": False, "flights": []}
    return {"available": True, "flights": state.db.get_history(limit=20)}


@app.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket) -> None:
    await ws.accept()
    if not await _ws_authorized(ws):
        await ws.close(code=4401)          # unauthorized: reject before honoring any command
        return

    async def receiver() -> None:
        try:
            while True:
                msg = await ws.receive_json()
                cmd = msg.get("command")
                if cmd:
                    try:
                        state.command(cmd, {k: v for k, v in msg.items() if k != "command"},
                                      plan_inline=False)
                        pending = getattr(state, "_pending_route", None)
                        if pending:                              # RRT* solve deferred: run it off-loop
                            e0, n0, u0, te, tn, alt = pending
                            path = await asyncio.to_thread(state._solve_route, (e0, n0, u0), te, tn, alt)
                            state.apply_route(path, te, tn, alt)
                        log.info("cmd %s -> mode=%s", cmd, state.mode)
                    except Exception as ex:                      # one bad command must not kill the loop
                        log.warning("cmd %s failed: %s", cmd, ex)
                        continue
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
    if not await _ws_authorized(ws):
        await ws.close(code=4401)
        return
    try:
        while True:
            await ws.send_json(state.threat_feed())
            await asyncio.sleep(0.5)
    except Exception:
        pass


# --- Unified single-port serving: this server ALSO serves the built GCS UI, so the
#     whole system runs as ONE process on ONE port (http://localhost:8080). ---
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse  # noqa: E402

_DIST = next(
    (d for d in (
        os.environ.get("SKYCORE_GCS_DIST", ""),
        os.path.join(_here, "..", "gcs-web", "dist"),   # consolidated/backend + consolidated/gcs-web
        os.path.join(_here, "gcs-web", "dist"),          # serve.py beside gcs-web/
    ) if d and os.path.isdir(d)),
    None,
)
if _DIST:
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def _spa(full_path: str) -> FileResponse:
        # Confine to _DIST: the {path} converter does NOT collapse `..`, so a raw
        # `GET /../../serve.py` would otherwise escape the dist dir and leak source/DB.
        root = os.path.realpath(_DIST)
        real = os.path.realpath(os.path.join(_DIST, full_path))
        if full_path and (real == root or real.startswith(root + os.sep)) and os.path.isfile(real):
            return FileResponse(real)
        return FileResponse(os.path.join(_DIST, "index.html"))
else:
    @app.get("/", response_class=HTMLResponse)
    async def _no_ui() -> str:
        return ("<h2>SkyCore backend running.</h2><p>GCS UI not built yet. Run the launch "
                "script, or build gcs-web with <code>npm run build</code>. "
                "APIs: /api/status, /telemetry, /threats; ws /ws/telemetry, /ws/threats.</p>")


if __name__ == "__main__":
    import uvicorn
    if HOST not in ("127.0.0.1", "localhost") and not os.environ.get("SKYCORE_JWT_SECRET"):
        log.warning("exposed on a non-loopback host with an ephemeral JWT secret; "
                    "set SKYCORE_JWT_SECRET (and real SKYCORE_USERS) for a stable deployment.")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
