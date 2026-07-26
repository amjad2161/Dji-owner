"""FastAPI application that exposes SkyCore over HTTP + WebSocket.

Serves:
- REST API for flight commands
- WebSocket for live telemetry
- Static dashboard (Leaflet map) at /
- Pre-flight checks: weather, terrain, geofence, full checklist
- Mission template generators
- Drone profiles, flight history, battery health
"""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from skycore.core.drone import Drone
from skycore.core.event_bus import EventBus
from skycore.core.types import GeoPoint, GeofenceConfig

log = logging.getLogger(__name__)

# Local-first defaults. The dashboard is intended for localhost, so auth is OPT-IN:
# set SKYCORE_API_TOKEN to require a bearer token (mandatory when not on loopback).
# CSRF is always enforced on mutating routes via a non-safelisted header + Origin check,
# so a random web page the pilot visits cannot drive the aircraft.
CSRF_HEADER = "x-skycore"


def create_app(drone: Drone, geofence: Optional[GeofenceConfig] = None, db_path: Optional[str] = None):
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
        from fastapi.encoders import jsonable_encoder
        from fastapi.exceptions import RequestValidationError
        from fastapi.responses import HTMLResponse, FileResponse
        from fastapi.staticfiles import StaticFiles
        from pydantic import BaseModel, Field
    except ImportError as e:
        raise ImportError("fastapi is required. pip install 'fastapi[standard]'") from e

    bus = EventBus()
    api_token = os.environ.get("SKYCORE_API_TOKEN", "")
    allowed_origins = {
        o.strip() for o in os.environ.get("SKYCORE_ALLOWED_ORIGINS", "").split(",") if o.strip()
    }

    def _origin_ok(origin: Optional[str], host: Optional[str]) -> bool:
        if not origin:
            return True                      # non-browser client (curl/CLI) sends no Origin
        if origin in allowed_origins:
            return True
        return urlparse(origin).netloc == (host or "")

    # NOTE: annotations are strings here (from __future__ import annotations) and these
    # names are imported inside create_app, so they must be resolvable when FastAPI
    # evaluates the signature — bind them into the function's globals namespace.
    globals().setdefault("Request", Request)
    globals().setdefault("Header", Header)

    async def guard(
        request: Request,
        authorization: str = Header(default=""),
        x_skycore: str = Header(default=""),
    ):
        """Protect every state-mutating route: CSRF (custom header + Origin) and,
        when SKYCORE_API_TOKEN is set, a bearer token."""
        if not _origin_ok(request.headers.get("origin"), request.headers.get("host")):
            raise HTTPException(status_code=403, detail="cross-origin request rejected")
        if not x_skycore:
            # A cross-site form/fetch cannot set this header without a CORS preflight,
            # which this app never grants -> blocks drive-by CSRF on flight commands.
            raise HTTPException(status_code=403, detail=f"missing {CSRF_HEADER} header")
        if api_token:
            if not authorization.startswith("Bearer ") or not secrets.compare_digest(
                authorization[7:], api_token
            ):
                raise HTTPException(status_code=401, detail="unauthorized")

    MUTATING = [Depends(guard)]

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await drone.connect()
        producer = asyncio.create_task(_telemetry_producer(drone, bus))
        try:
            yield
        finally:
            producer.cancel()
            await drone.disconnect()

    app = FastAPI(title="SkyCore", version="0.3.0", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request, exc):
        # The default handler echoes the offending input back; a rejected NaN/Infinity
        # then crashes JSON serialisation. Return the errors without the raw input.
        from fastapi.responses import JSONResponse
        clean = [{k: v for k, v in e.items() if k != "input"} for e in exc.errors()]
        return JSONResponse(status_code=422, content=jsonable_encoder({"detail": clean}))

    # Bounded + finite: Python's JSON decoder accepts NaN/Infinity and Pydantic allows
    # them by default, so {"lat": NaN} previously passed validation AND bypassed the
    # geofence (every comparison with NaN is False).
    class GotoRequest(BaseModel):
        lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
        lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
        alt: float = Field(default=30.0, ge=0, le=10000, allow_inf_nan=False)
        speed: float = Field(default=5.0, gt=0, le=30, allow_inf_nan=False)

    class VelocityRequest(BaseModel):
        vx: float = Field(default=0.0, ge=-30, le=30, allow_inf_nan=False)
        vy: float = Field(default=0.0, ge=-30, le=30, allow_inf_nan=False)
        vz: float = Field(default=0.0, ge=-15, le=15, allow_inf_nan=False)
        yaw_rate: float = Field(default=0.0, ge=-180, le=180, allow_inf_nan=False)

    class TakeoffRequest(BaseModel):
        altitude: float = Field(default=5.0, gt=0, le=10000, allow_inf_nan=False)

    class WeatherQuery(BaseModel):
        lat: float
        lon: float
        max_wind_kph: float = 36.0
        max_gust_kph: float = 50.0

    class ElevationQuery(BaseModel):
        lat: float
        lon: float

    class ChecklistRequest(BaseModel):
        max_wind_kph: float = 36.0
        min_battery_percent: float = 90.0
        min_gps_satellites: int = 12

    class TemplateRequest(BaseModel):
        kind: str  # "orbit" | "panorama" | "perimeter" | "building" | "hyperlapse" | "facade" | "reveal" | "spiral"
        params: dict = {}

    # These models are defined inside create_app but referenced in route signatures as
    # STRING annotations (from __future__ import annotations). FastAPI resolves those
    # against the module globals, so publish them there or every body param is mistaken
    # for a required query param (422).
    for _m in (GotoRequest, VelocityRequest, TakeoffRequest, WeatherQuery,
               ElevationQuery, ChecklistRequest, TemplateRequest):
        globals()[_m.__name__] = _m

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "drone": drone.name, "connected": drone.is_connected, "version": "0.3.0"}

    @app.get("/api/telemetry")
    async def telemetry():
        tm = await drone.get_telemetry()
        return tm.to_dict()

    @app.post("/api/takeoff", dependencies=MUTATING)
    async def takeoff(req: TakeoffRequest):
        if geofence and req.altitude > geofence.max_altitude_m:
            return {"error": f"altitude {req.altitude} exceeds geofence {geofence.max_altitude_m}"}
        await drone.takeoff(altitude_m=req.altitude)
        return {"ok": True}

    @app.post("/api/land", dependencies=MUTATING)
    async def land():
        await drone.land()
        return {"ok": True}

    @app.post("/api/rth", dependencies=MUTATING)
    async def rth():
        await drone.return_to_home()
        return {"ok": True}

    @app.post("/api/goto", dependencies=MUTATING)
    async def goto(req: GotoRequest):
        target = GeoPoint(req.lat, req.lon, req.alt)
        if geofence and geofence.home and geofence.home.haversine_m(target) > geofence.max_radius_m:
            return {"error": "target outside geofence radius"}
        await drone.goto(target, speed_mps=req.speed)
        return {"ok": True}

    @app.post("/api/velocity", dependencies=MUTATING)
    async def velocity(req: VelocityRequest):
        await drone.set_velocity(req.vx, req.vy, req.vz, req.yaw_rate)
        return {"ok": True}

    @app.post("/api/photo", dependencies=MUTATING)
    async def photo():
        uri = await drone.take_photo()
        return {"uri": uri}

    @app.post("/api/record/start", dependencies=MUTATING)
    async def record_start():
        await drone.start_recording()
        return {"ok": True}

    @app.post("/api/record/stop", dependencies=MUTATING)
    async def record_stop():
        await drone.stop_recording()
        return {"ok": True}

    @app.post("/api/preflight/weather")
    async def preflight_weather(req: WeatherQuery):
        from skycore.weather import preflight_check
        loop = asyncio.get_running_loop()
        ok, issues, snap = await loop.run_in_executor(
            None, preflight_check, req.lat, req.lon, req.max_wind_kph, req.max_gust_kph
        )
        return {
            "ok": ok,
            "issues": issues,
            "weather": {
                "temperature_c": snap.temperature_c,
                "wind_kph": snap.wind_speed_kph,
                "gust_kph": snap.wind_gust_kph,
                "wind_direction": snap.wind_direction_deg,
                "precipitation_mm_h": snap.precipitation_mm_h,
                "cloud_pct": snap.cloud_cover_pct,
                "pressure_hpa": snap.pressure_hpa,
                "humidity_pct": snap.humidity_pct,
            },
        }

    @app.post("/api/preflight/elevation")
    async def preflight_elevation(req: ElevationQuery):
        from skycore.terrain import get_elevation
        loop = asyncio.get_running_loop()
        e = await loop.run_in_executor(None, get_elevation, req.lat, req.lon)
        return {"elevation_m_amsl": e}

    @app.post("/api/preflight/checklist")
    async def preflight_checklist(req: ChecklistRequest):
        from skycore.checklist import PreflightChecklist
        home = geofence.home if (geofence and geofence.home) else None
        cl = PreflightChecklist(
            drone=drone,
            home=home,
            max_wind_kph=req.max_wind_kph,
            min_battery_percent=req.min_battery_percent,
            min_gps_satellites=req.min_gps_satellites,
        )
        report = await cl.run()
        return report.to_dict()

    @app.post("/api/missions/template")
    async def missions_template(req: TemplateRequest):
        """Generate a mission from a template; returns waypoints as JSON."""
        from skycore.templates import (
            panorama_mission, perimeter_patrol, building_inspection,
            hyperlapse_line, vertical_panorama, spiraling_orbit,
            facade_scan, cinematic_reveal,
        )
        from skycore.missions.orbit import orbit_mission
        p = req.params
        try:
            if req.kind == "orbit":
                m = orbit_mission(GeoPoint(p["lat"], p["lon"]), radius_m=p.get("radius", 50), altitude_m=p.get("altitude", 30), waypoints=p.get("waypoints", 12))
            elif req.kind == "panorama":
                m = panorama_mission(GeoPoint(p["lat"], p["lon"]), altitude_m=p.get("altitude", 30), yaw_steps=p.get("yaw_steps", 12))
            elif req.kind == "perimeter":
                pts = [GeoPoint(c["lat"], c["lon"]) for c in p["corners"]]
                m = perimeter_patrol(pts, altitude_m=p.get("altitude", 40))
            elif req.kind == "building":
                m = building_inspection(GeoPoint(p["lat"], p["lon"]), radius_m=p.get("radius", 25))
            elif req.kind == "hyperlapse":
                m = hyperlapse_line(GeoPoint(p["start_lat"], p["start_lon"]), GeoPoint(p["end_lat"], p["end_lon"]), altitude_m=p.get("altitude", 30))
            elif req.kind == "facade":
                m = facade_scan(GeoPoint(p["start_lat"], p["start_lon"]), GeoPoint(p["end_lat"], p["end_lon"]))
            elif req.kind == "reveal":
                m = cinematic_reveal(GeoPoint(p["fg_lat"], p["fg_lon"]), GeoPoint(p["bg_lat"], p["bg_lon"]))
            elif req.kind == "spiral":
                m = spiraling_orbit(GeoPoint(p["lat"], p["lon"]))
            elif req.kind == "vertical_pano":
                m = vertical_panorama(GeoPoint(p["lat"], p["lon"]), altitude_m=p.get("altitude", 30))
            else:
                return {"error": f"unknown template kind: {req.kind}"}
        except (KeyError, ValueError) as e:
            log.warning("template request failed: %s", e)     # detail stays server-side
            return {"error": f"invalid or missing parameters for template '{req.kind}'"}
        return {
            "name": m.name,
            "waypoints": [
                {"lat": s.target.lat, "lon": s.target.lon, "alt": s.target.alt, "speed": s.speed_mps,
                 "yaw": s.yaw_deg, "gimbal_pitch": s.gimbal_pitch_deg, "actions": list(s.actions)}
                for s in m.steps
            ],
        }

    @app.get("/api/profiles")
    async def profiles():
        from skycore.profiles import all_profiles
        return {
            "profiles": [
                {
                    "model": p.model, "family": p.family, "weight_g": p.weight_g,
                    "max_horiz_speed_mps": p.max_horiz_speed_mps,
                    "max_wind_resistance_kph": p.max_wind_resistance_kph,
                    "max_flight_time_min": p.max_flight_time_min,
                    "max_video_resolution": p.max_video_resolution,
                    "transmission": p.transmission,
                    "sdk_support": list(p.sdk_support),
                }
                for p in all_profiles()
            ]
        }

    @app.get("/api/flights")
    async def list_flights():
        if not db_path:
            return {"flights": [], "note": "no db configured"}
        from skycore.storage import FlightDatabase

        def _read():                    # blocking sqlite off the event loop
            with FlightDatabase(db_path) as fdb:
                return fdb.list_flights(50)
        loop = asyncio.get_running_loop()
        return {"flights": await loop.run_in_executor(None, _read)}

    @app.get("/api/batteries")
    async def list_batteries():
        from skycore.battery import BatteryRegistry
        path = (db_path or "skycore.db").replace("flights.db", "batteries.db")

        def _read():                    # blocking sqlite off the event loop
            with BatteryRegistry(path) as reg:
                return [
                    {"serial": h.serial, "cycles": h.cycles, "heavy_dod": h.heavy_discharge_count,
                     "health_pct": h.estimated_health_pct, "avg_min_voltage": h.avg_min_voltage,
                     "last_used": h.last_used}
                    for h in reg.list_all() if h is not None
                ]
        try:
            loop = asyncio.get_running_loop()
            return {"batteries": await loop.run_in_executor(None, _read)}
        except Exception:
            log.exception("battery registry read failed")   # log detail server-side only
            return {"batteries": [], "error": "battery registry unavailable"}

    @app.websocket("/ws/telemetry")
    async def ws_telemetry(ws: WebSocket):
        # Browsers do NOT apply same-origin policy to WebSocket opens, so without this
        # any page the pilot visits could stream live GPS/telemetry (CSWSH).
        if not _origin_ok(ws.headers.get("origin"), ws.headers.get("host")):
            await ws.close(code=4403)
            return
        if api_token and not secrets.compare_digest(ws.query_params.get("token", ""), api_token):
            await ws.close(code=4401)
            return
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
