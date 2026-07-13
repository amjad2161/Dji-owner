"""
SkyCore live simulator backend.

Serves telemetry + accepts flight commands over WebSocket in the exact shape
the SkyCore GCS web app expects (ws://<host>:8080/ws/telemetry).

This is an HONEST SIMULATOR: every telemetry frame carries source="simulator".
Values evolve over real time (battery drains, altitude climbs, the aircraft
moves toward waypoints) so the GCS shows genuinely live, changing data — but it
is a physics-lite simulation, not a physical drone. No hardware is claimed.

Run:  python serve.py           # listens on 0.0.0.0:8080
Deps: fastapi, uvicorn[standard]
"""
from __future__ import annotations

import asyncio
import math
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# --- Optional: use the real canonical SimulatorDrone if it can be imported,
#     purely to report provenance honestly (like reference/sky.py does). The
#     live evolution below is authoritative either way. ---
BACKEND = "builtin-sim"
try:  # pragma: no cover - best effort, never fatal
    import os, sys
    _here = os.path.dirname(os.path.abspath(__file__))
    for _cand in (
        os.environ.get("SKYCORE_PKG", ""),
        os.path.join(_here, "..", "src", "skycore_v1.0.0", "skycore"),
        os.path.join(_here, "skycore"),
    ):
        if _cand and os.path.isdir(_cand):
            sys.path.insert(0, _cand)
            from core.drone import SimulatorDrone  # noqa: F401
            BACKEND = "skycore.core.drone.SimulatorDrone"
            break
except Exception:
    BACKEND = "builtin-sim"

HOME_LAT, HOME_LON = 32.0853, 34.7818  # Tel Aviv
CLIMB_RATE = 2.5    # m/s
CRUISE_SPEED = 9.0  # m/s
BATTERY_DRAIN = 0.06  # % per second while armed/airborne
TICK_HZ = 10.0

M_PER_DEG_LAT = 111_320.0


class SimState:
    def __init__(self) -> None:
        self.mode = "DISARMED"      # DISARMED|ARMED|TAKEOFF|FLYING|LANDING|RTL
        self.armed = False
        self.lat = HOME_LAT
        self.lon = HOME_LON
        self.alt = 0.0
        self.target_alt = 0.0
        self.target_lat: float | None = None
        self.target_lon: float | None = None
        self.battery = 100.0
        self.speed = 0.0
        self.heading = 0.0
        self._t = time.monotonic()

    # ---- command handling (mirrors GCS TelemetryService.sendCommand) ----
    def command(self, cmd: str, p: dict) -> None:
        airborne = self.alt > 0.5 or self.mode in ("TAKEOFF", "FLYING", "RTL")
        if cmd == "arm" and not airborne:
            self.armed, self.mode = True, "ARMED"
        elif cmd == "disarm" and not airborne:
            self.armed, self.mode = False, "DISARMED"
        elif cmd == "takeoff":
            if not self.armed:
                self.armed = True
            self.target_alt = float(p.get("altitude", 30.0))
            self.mode = "TAKEOFF"
        elif cmd == "land":
            self.target_lat = self.target_lon = None
            self.target_alt = 0.0
            self.mode = "LANDING"
        elif cmd == "rtl":
            self.target_lat, self.target_lon = HOME_LAT, HOME_LON
            self.mode = "RTL"
        elif cmd == "goto" and airborne:
            self.target_lat = float(p["lat"])
            self.target_lon = float(p["lon"])
            self.target_alt = float(p.get("altitude", self.alt))
            self.mode = "FLYING"

    # ---- time evolution ----
    def step(self) -> None:
        now = time.monotonic()
        dt = now - self._t
        self._t = now
        if dt <= 0:
            return

        if self.armed and (self.alt > 0.1 or self.mode in ("TAKEOFF", "FLYING", "RTL", "LANDING")):
            self.battery = max(0.0, self.battery - BATTERY_DRAIN * dt)
        if self.battery <= 0.0 and self.mode not in ("DISARMED",):
            self.mode = "LANDING"
            self.target_lat = self.target_lon = None
            self.target_alt = 0.0

        # vertical
        if abs(self.alt - self.target_alt) > 0.05:
            step = CLIMB_RATE * dt
            self.alt += math.copysign(min(step, abs(self.target_alt - self.alt)), self.target_alt - self.alt)
        else:
            self.alt = self.target_alt

        # horizontal
        self.speed = 0.0
        if self.target_lat is not None and self.target_lon is not None and self.alt > 0.5:
            dlat_m = (self.target_lat - self.lat) * M_PER_DEG_LAT
            dlon_m = (self.target_lon - self.lon) * M_PER_DEG_LAT * math.cos(math.radians(self.lat))
            dist = math.hypot(dlat_m, dlon_m)
            if dist > 1.0:
                move = min(CRUISE_SPEED * dt, dist)
                self.speed = move / dt
                self.heading = (math.degrees(math.atan2(dlon_m, dlat_m)) + 360) % 360
                self.lat += (dlat_m / dist) * move / M_PER_DEG_LAT
                self.lon += (dlon_m / dist) * move / (M_PER_DEG_LAT * math.cos(math.radians(self.lat)))
            else:
                self.lat, self.lon = self.target_lat, self.target_lon
                self.target_lat = self.target_lon = None

        # mode transitions
        if self.mode == "TAKEOFF" and self.alt >= self.target_alt - 0.1:
            self.mode = "FLYING"
        elif self.mode == "RTL" and self.target_lat is None and self.alt > 0.5:
            self.target_alt, self.mode = 0.0, "LANDING"
        elif self.mode == "LANDING" and self.alt <= 0.1:
            self.alt, self.armed, self.mode, self.speed = 0.0, False, "DISARMED", 0.0

    def snapshot(self) -> dict:
        return {
            "source": "simulator",
            "backend": BACKEND,
            "mode": self.mode,
            "armed": self.armed,
            "battery": {"percent": round(self.battery, 1)},
            "position": {"lat": round(self.lat, 6), "lon": round(self.lon, 6), "altitude": round(self.alt, 1)},
            "velocity": {"speed": round(self.speed, 1)},
            "attitude": {"yaw": round(self.heading, 1)},
        }


state = SimState()
app = FastAPI(title="SkyCore Live Simulator Backend", version="1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.on_event("startup")
async def _start_sim_loop() -> None:
    async def loop() -> None:
        while True:
            state.step()
            await asyncio.sleep(1.0 / TICK_HZ)
    asyncio.create_task(loop())


@app.get("/")
async def root() -> dict:
    return {"service": "SkyCore Live Simulator Backend", "status": "running", "backend": BACKEND}


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
                    params = {k: v for k, v in msg.items() if k != "command"}
                    state.command(cmd, params)
                    print(f"[cmd] {cmd} {params} -> mode={state.mode}")
        except (WebSocketDisconnect, Exception):
            return

    recv = asyncio.create_task(receiver())
    try:
        while True:
            await ws.send_json(state.snapshot())
            await asyncio.sleep(0.2)  # 5 Hz
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        recv.cancel()


if __name__ == "__main__":
    import uvicorn
    print(f"SkyCore live simulator backend on http://0.0.0.0:8080  (provenance backend: {BACKEND})")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
