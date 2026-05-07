"""FastAPI application that exposes SkyCore over HTTP + WebSocket.

Serves:
- REST API for commands (takeoff, land, goto, etc.)
- WebSocket for live telemetry
- Static dashboard (single HTML/JS page) at /

The app is parameterized by a Drone instance so you can wire up any backend.
Start it with `skycore serve` from the CLI, which defaults to the simulator.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from skycore.core.drone import Drone
from skycore.core.event_bus import EventBus
from skycore.core.types import GeoPoint, GeofenceConfig

log = logging.getLogger(__name__)


def create_app(drone: Drone, geofence: Optional[GeofenceConfig] = None):
    try:
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import HTMLResponse, FileResponse
        from fastapi.staticfiles import StaticFiles
        from pydantic import BaseModel
    except ImportError as e:
        raise ImportError(
            "fastapi is required. Install with: pip install 'fastapi[standard]'"
        ) from e

    bus = EventBus()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await drone.connect()
        producer = asyncio.create_task(_telemetry_producer(drone, bus))
        try:
            yield
        finally:
            producer.cancel()
            await drone.disconnect()

    app = FastAPI(title="SkyCore", version="0.1.0", lifespan=lifespan)

    class GotoRequest(BaseModel):
        lat: float
        lon: float
        alt: float = 30.0
        speed: float = 5.0

    class VelocityRequest(BaseModel):
        vx: float = 0.0
        vy: float = 0.0
        vz: float = 0.0
        yaw_rate: float = 0.0

    class TakeoffRequest(BaseModel):
        altitude: float = 5.0

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "drone": drone.name, "connected": drone.is_connected}

    @app.get("/api/telemetry")
    async def telemetry():
        tm = await drone.get_telemetry()
        return tm.to_dict()

    @app.post("/api/takeoff")
    async def takeoff(req: TakeoffRequest):
        if geofence and req.altitude > geofence.max_altitude_m:
            return {"error": f"altitude {req.altitude} exceeds geofence {geofence.max_altitude_m}"}
        await drone.takeoff(altitude_m=req.altitude)
        return {"ok": True}

    @app.post("/api/land")
    async def land():
        await drone.land()
        return {"ok": True}

    @app.post("/api/rth")
    async def rth():
        await drone.return_to_home()
        return {"ok": True}

    @app.post("/api/goto")
    async def goto(req: GotoRequest):
        target = GeoPoint(req.lat, req.lon, req.alt)
        if geofence and geofence.home and geofence.home.haversine_m(target) > geofence.max_radius_m:
            return {"error": "target outside geofence radius"}
        await drone.goto(target, speed_mps=req.speed)
        return {"ok": True}

    @app.post("/api/velocity")
    async def velocity(req: VelocityRequest):
        await drone.set_velocity(req.vx, req.vy, req.vz, req.yaw_rate)
        return {"ok": True}

    @app.post("/api/photo")
    async def photo():
        uri = await drone.take_photo()
        return {"uri": uri}

    @app.post("/api/record/start")
    async def record_start():
        await drone.start_recording()
        return {"ok": True}

    @app.post("/api/record/stop")
    async def record_stop():
        await drone.stop_recording()
        return {"ok": True}

    @app.websocket("/ws/telemetry")
    async def ws_telemetry(ws: WebSocket):
        await ws.accept()
        q = bus.subscribe("telemetry")
        try:
            while True:
                msg = await q.get()
                await ws.send_json(msg)
        except WebSocketDisconnect:
            pass
        finally:
            bus.unsubscribe("telemetry", q)

    @app.get("/")
    async def root():
        ui = Path(__file__).parent / "web" / "index.html"
        if ui.exists():
            return FileResponse(ui)
        return HTMLResponse(_FALLBACK_HTML)

    web_dir = Path(__file__).parent / "web"
    if web_dir.exists():
        app.mount("/static", StaticFiles(directory=web_dir), name="static")

    return app


async def _telemetry_producer(drone: Drone, bus: EventBus) -> None:
    try:
        async for tm in drone.telemetry_stream():
            await bus.publish("telemetry", tm.to_dict())
    except asyncio.CancelledError:
        return
    except Exception as e:  # pragma: no cover
        log.error("telemetry producer crashed: %s", e)


_FALLBACK_HTML = """<!doctype html>
<html><head><title>SkyCore</title></head>
<body style='font-family:system-ui;max-width:600px;margin:40px auto'>
<h1>SkyCore is running</h1>
<p>UI not bundled. Use the API directly or visit <a href='/docs'>/docs</a> for OpenAPI.</p>
</body></html>
"""
