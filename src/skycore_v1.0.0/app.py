"""FastAPI application that exposes SkyCore over HTTP + WebSocket.

Serves:
- REST API for flight commands
- WebSocket for live telemetry
- Static dashboard (Leaflet map) at /
- Pre-flight checks: weather, terrain, geofence, full checklist
- Mission template generators
- Drone profiles, flight history, battery health
- C-UAS threat detection and swarm coordination
- Security operator control and audit logging
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from skycore.core.drone import Drone
from skycore.core.event_bus import EventBus
from skycore.core.types import GeoPoint, GeofenceConfig

log = logging.getLogger(__name__)


# Rate limiting configuration
RATE_LIMIT_REQUESTS = 100  # requests per window
RATE_LIMIT_WINDOW_S = 60   # time window in seconds


class RateLimitMiddleware:
    """Simple in-memory rate limiter.
    
    Tracks requests per IP address and blocks excessive requests.
    """
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
    
    async def __call__(self, scope, receive, send):
        """ASGI middleware."""
        # Get client IP
        client_ip = "unknown"
        if scope.get("client"):
            client_ip = scope["client"][0]
        
        now = time.time()
        
        # Clean old requests
        self._requests[client_ip] = [
            t for t in self._requests[client_ip]
            if now - t < self.window_seconds
        ]
        
        # Check rate
        if len(self._requests[client_ip]) >= self.max_requests:
            # Rate limited
            await self._rate_limit_response(send)
            return
        
        # Record request
        self._requests[client_ip].append(now)
        
        # Continue to next middleware
        await self._app(scope, receive, send)
    
    async def set_app(self, app):
        """Set the next ASGI app."""
        self._app = app
    
    async def _rate_limit_response(self, send):
        """Send 429 Too Many Requests response."""
        await send({
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"content-type", b"application/json"),
                (b"retry-after", b"60"),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"error": "Rate limit exceeded. Max 100 requests per minute."}',
        })


# Global rate limiter instance
_rate_limiter = RateLimitMiddleware(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_S)


def create_app(drone: Drone, geofence: Optional[GeofenceConfig] = None, db_path: Optional[str] = None):
    try:
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
        from fastapi.responses import HTMLResponse, FileResponse
        from fastapi.staticfiles import StaticFiles
        from fastapi.middleware.base import BaseHTTPMiddleware
        from pydantic import BaseModel
    except ImportError as e:
        raise ImportError("fastapi is required. pip install 'fastapi[standard]'") from e

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

    app = FastAPI(title="SkyCore", version="0.4.0", lifespan=lifespan)

    # Add rate limiting middleware
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        """Apply rate limiting to all requests."""
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Get or create rate limit data for this IP
        if not hasattr(rate_limit_middleware, "_ip_data"):
            rate_limit_middleware._ip_data = {}
        
        ip_data = rate_limit_middleware._ip_data
        if client_ip not in ip_data:
            ip_data[client_ip] = {"requests": [], "blocked_until": 0}
        
        user_data = ip_data[client_ip]
        
        # Clean old requests
        user_data["requests"] = [
            t for t in user_data["requests"]
            if now - t < RATE_LIMIT_WINDOW_S
        ]
        
        # Check if blocked
        if now < user_data["blocked_until"]:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Max 100 requests per minute."},
                headers={"Retry-After": str(int(user_data["blocked_until"] - now))}
            )
        
        # Check rate
        if len(user_data["requests"]) >= RATE_LIMIT_REQUESTS:
            user_data["blocked_until"] = now + RATE_LIMIT_WINDOW_S
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Max 100 requests per minute."},
                headers={"Retry-After": str(RATE_LIMIT_WINDOW_S)}
            )
        
        # Record request
        user_data["requests"].append(now)
        
        response = await call_next(request)
        return response

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

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "drone": drone.name, "connected": drone.is_connected, "version": "0.3.0"}

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
            return {"error": str(e)}
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
        with FlightDatabase(db_path) as fdb:
            return {"flights": fdb.list_flights(50)}

    @app.get("/api/batteries")
    async def list_batteries():
        from skycore.battery import BatteryRegistry
        path = (db_path or "skycore.db").replace("flights.db", "batteries.db")
        try:
            with BatteryRegistry(path) as reg:
                return {"batteries": [
                    {"serial": h.serial, "cycles": h.cycles, "heavy_dod": h.heavy_discharge_count,
                     "health_pct": h.estimated_health_pct, "avg_min_voltage": h.avg_min_voltage,
                     "last_used": h.last_used}
                    for h in reg.list_all() if h is not None
                ]}
        except Exception as e:
            return {"batteries": [], "error": str(e)}

    @app.post("/api/batteries/register")
    async def register_battery(serial: str, firmware: str = "", manufactured_date: str = None):
        from skycore.battery import BatteryRegistry
        path = (db_path or "skycore.db").replace("flights.db", "batteries.db")
        try:
            with BatteryRegistry(path) as reg:
                reg.register(serial, firmware, manufactured_date)
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/batteries/{serial}")
    async def get_battery_health(serial: str):
        from skycore.battery import BatteryRegistry
        path = (db_path or "skycore.db").replace("flights.db", "batteries.db")
        try:
            with BatteryRegistry(path) as reg:
                h = reg.get_health(serial)
                if h is None:
                    return {"error": "battery not found"}
                needs_replacement, reason = reg.needs_replacement(serial)
                return {
                    "battery": h.to_dict(),
                    "needs_replacement": needs_replacement,
                    "replacement_reason": reason,
                }
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/batteries/{serial}/charge/start")
    async def battery_charge_start(serial: str):
        from skycore.battery import BatteryRegistry
        path = (db_path or "skycore.db").replace("flights.db", "batteries.db")
        try:
            with BatteryRegistry(path) as reg:
                reg.log_charge_start(serial)
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/batteries/{serial}/charge/end")
    async def battery_charge_end(serial: str, end_pct: float = 100, health_pct: float = None, voltage_sag: float = None):
        from skycore.battery import BatteryRegistry
        path = (db_path or "skycore.db").replace("flights.db", "batteries.db")
        try:
            with BatteryRegistry(path) as reg:
                reg.log_charge_end(serial, end_pct, health_pct, voltage_sag)
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/odm/status")
    async def odm_status():
        """Check if ODM Docker is available."""
        import shutil
        return {"docker_available": shutil.which("docker") is not None}

    @app.post("/api/odm/process")
    async def odm_process(images_dir: str, orthophoto_resolution: int = 5, fast: bool = False):
        """Start ODM processing (runs async)."""
        from pathlib import Path
        from skycore.odm import run_odm_docker, ODMResult
        loop = asyncio.get_running_loop()
        try:
            def do_run():
                return run_odm_docker(Path(images_dir), orthophoto_resolution, dsm=True, fast=fast)
            result: ODMResult = await loop.run_in_executor(None, do_run)
            return {
                "ok": True,
                "output_dir": str(result.output_dir),
                "orthophoto": str(result.orthophoto) if result.orthophoto else None,
                "dsm": str(result.dsm) if result.dsm else None,
            }
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/hdr/merge")
    async def hdr_merge(image_paths: list[str], output_path: str, method: str = "mertens"):
        """Merge bracketed images into HDR."""
        from pathlib import Path
        from skycore.hdr import merge_hdr
        loop = asyncio.get_running_loop()
        try:
            def do_merge():
                merge_hdr([Path(p) for p in image_paths], Path(output_path), method=method)
            await loop.run_in_executor(None, do_merge)
            return {"ok": True, "output": output_path}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/fleet/drones")
    async def fleet_list():
        """List all connected drones in the fleet."""
        return {"drones": [], "note": "Fleet management via dedicated CLI"}

    @app.post("/api/geotag")
    async def geotag_photos(photos_dir: str, telemetry_csv: str, output_dir: str = None):
        """Geotag photos from telemetry CSV."""
        from pathlib import Path
        from skycore.geotag import geotag_from_telemetry
        loop = asyncio.get_running_loop()
        try:
            out = output_dir or str(Path(photos_dir) / "geotagged")
            def do_geotag():
                geotag_from_telemetry(Path(photos_dir), Path(telemetry_csv), Path(out))
            await loop.run_in_executor(None, do_geotag)
            return {"ok": True, "output_dir": out}
        except Exception as e:
            return {"error": str(e)}

    # ========== SECURITY & OPERATOR CONTROL ==========

    @app.post("/api/security/authenticate")
    async def security_authenticate(operator_id: str, credentials: str, ip_address: str = None):
        """Authenticate an operator for command execution."""
        from security.operator_control import default_operator_control
        result = default_operator_control.authenticate_operator(operator_id, credentials, ip_address)
        return result

    @app.post("/api/security/command")
    async def security_command(session_id: str, command: dict):
        """Execute a command with operator validation."""
        from security.operator_control import default_operator_control
        from security.immutable_audit import log_command_event
        result = default_operator_control.execute_command(session_id, command)
        if result.get("success"):
            log_command_event(command.get("type", ""), command, session_id, "SUCCESS")
        return result

    @app.post("/api/security/lockdown")
    async def security_lockdown(session_id: str):
        """Initiate emergency lockdown."""
        from security.operator_control import default_operator_control
        success = default_operator_control.emergency_lockdown(session_id)
        return {"success": success, "locked": default_operator_control._locked}

    @app.post("/api/security/unlock")
    async def security_unlock(session_id: str):
        """Unlock the system after lockdown."""
        from security.operator_control import default_operator_control
        success = default_operator_control.unlock_system(session_id)
        return {"success": success, "locked": default_operator_control._locked}

    @app.get("/api/security/sessions")
    async def security_sessions():
        """Get active operator sessions."""
        from security.operator_control import default_operator_control
        return {"sessions": default_operator_control.get_active_sessions()}

    @app.get("/api/security/history")
    async def security_history(limit: int = 50):
        """Get command history."""
        from security.operator_control import default_operator_control
        return {"history": default_operator_control.get_command_history(limit)}

    @app.get("/api/security/audit")
    async def security_audit(event_type: str = None, actor: str = None, limit: int = 100):
        """Query immutable audit log."""
        from security.immutable_audit import default_audit
        return {"audit": default_audit.get_audit_trail(limit, event_type, actor)}

    @app.get("/api/security/audit/verify")
    async def security_audit_verify():
        """Verify audit chain integrity."""
        from security.immutable_audit import default_audit
        return default_audit.verify_chain()

    @app.get("/api/security/stats")
    async def security_stats():
        """Get audit log statistics."""
        from security.immutable_audit import default_audit
        return default_audit.get_statistics()

    # ========== AIRSPACE AWARENESS (ADS-B) ==========

    @app.post("/api/awareness/airspace")
    async def awareness_check(lat: float, lon: float, radius_km: float = 10.0):
        """Quick airspace check for manned aircraft."""
        from awareness.adsb import AirspaceMonitor
        
        # Create monitor and run synchronously in executor (API is async)
        def fetch_aircraft():
            monitor = AirspaceMonitor()
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(monitor._fetch_and_update(lat, lon, radius_km))
            finally:
                loop.close()
            return [c.icao24 for c in monitor._contacts.values()]
        
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = list(executor.submit(fetch_aircraft).result())
        
        return {"aircraft": result, "checked_radius_km": radius_km}

    @app.get("/api/awareness/alerts")
    async def awareness_alerts(lat: float, lon: float, altitude_m: float = 50.0):
        """Get airspace conflict alerts for drone position."""
        from awareness.adsb import default_monitor
        alerts = default_monitor.get_nearby(lat, lon, altitude_m)
        return {
            "alerts": [
                {
                    "icao": a.aircraft.icao24,
                    "callsign": a.aircraft.callsign,
                    "distance_m": a.distance_m,
                    "altitude_sep_m": a.altitude_separation_m,
                    "time_to_approach_s": a.time_to_closest_approach_s,
                    "threat_level": a.threat_level,
                    "action": a.recommended_action,
                }
                for a in alerts
            ]
        }

    # ========== DEFENSE / RF SCANNING ==========

    @app.post("/api/defense/scan")
    async def defense_scan(duration_s: float = 10.0):
        """Perform RF environment scan."""
        from defense.rf_scanner import RFScanner
        
        scanner = RFScanner()
        
        # Run async scan in thread executor (cleaner than nested event loop)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = executor.submit(lambda: asyncio.run(scanner.scan_environment(duration_s))).result()
        
        return result

    @app.post("/api/defense/preflight")
    async def defense_preflight(lat: float, lon: float):
        """Pre-flight signal check."""
        from defense.rf_scanner import preflight_signal_check
        
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = executor.submit(lambda: asyncio.run(preflight_signal_check(lat, lon))).result()
        
        return result

    # ========== THREAT PREDICTION (C-UAS) ==========

    @app.post("/api/cuas/track")
    async def cuas_track(drone_id: str, lat: float, lon: float, alt: float):
        """Track a drone for threat prediction."""
        from cuas.threat_prediction import default_predictor
        default_predictor.track(drone_id, lat, lon, alt)
        return {"tracked": drone_id, "position": {"lat": lat, "lon": lon, "alt": alt}}

    @app.post("/api/cuas/predict")
    async def cuas_predict(our_lat: float, our_lon: float, our_alt: float, prediction_time_s: float = 10.0):
        """Predict threats based on tracked trajectories."""
        from cuas.threat_prediction import default_predictor
        predictions = default_predictor.predict_all(our_lat, our_lon, our_alt, prediction_time_s)
        return {
            "predictions": [p.to_dict() for p in predictions],
            "count": len(predictions),
        }

    # ========== SWARM COORDINATION ==========

    @app.post("/api/swarm/drone")
    async def swarm_add_drone(drone_id: str, lat: float, lon: float, alt: float, role: str = "follower"):
        """Add a drone to the swarm."""
        from swarm.coordinator import default_swarm
        default_swarm.add_drone(drone_id, lat, lon, alt, role)
        return {"added": drone_id, "role": role}

    @app.get("/api/swarm/status")
    async def swarm_status():
        """Get swarm status."""
        from swarm.coordinator import default_swarm
        return default_swarm.get_swarm_status()

    @app.post("/api/swarm/formation")
    async def swarm_set_formation(center_lat: float, center_lon: float, center_alt: float = 50.0,
                                   formation_type: str = "circle"):
        """Set swarm formation center and type."""
        from swarm.coordinator import default_swarm
        center = (center_lat, center_lon, center_alt)
        result = await default_swarm.set_formation(center, formation_type)
        return result

    @app.post("/api/swarm/emergency")
    async def swarm_emergency():
        """Emergency stop all swarm drones (RTL)."""
        from swarm.coordinator import default_swarm
        return default_swarm.emergency_stop_all()

    # ========== DRONE PROTOCOL DETECTION ==========

    @app.get("/api/protocol/drones")
    async def protocol_get_drones():
        """Get all detected drones."""
        from protocol.drone_detector import default_detector
        drones = default_detector.get_detected_drones()
        return {
            "drones": [
                {
                    "id": d.drone_id,
                    "protocol": d.protocol.value,
                    "type": d.drone_type.value,
                    "confirmed": d.is_confirmed,
                    "confidence": round(d.confidence, 3),
                    "pulse_count": d.pulse_count,
                    "last_seen_s": time.time() - d.last_pulse,
                    "pulse_interval_ms": d.pulse_interval_ms,
                }
                for d in drones
            ],
            "count": len(drones),
        }

    @app.get("/api/protocol/drone/{drone_id}")
    async def protocol_get_drone(drone_id: str):
        """Get specific drone details."""
        from protocol.drone_detector import default_detector
        drone = default_detector.get_drone(drone_id)
        if not drone:
            return {"error": "Drone not found"}
        return {
            "id": drone.drone_id,
            "protocol": drone.protocol.value,
            "type": drone.drone_type.value,
            "confirmed": drone.is_confirmed,
            "confidence": round(drone.confidence, 3),
            "pulse_count": drone.pulse_count,
            "first_seen": drone.first_seen,
            "last_pulse": drone.last_pulse,
            "pulse_interval_ms": drone.pulse_interval_ms,
            "position": drone.position_latest,
        }

    @app.post("/api/protocol/record")
    async def protocol_record_pulse(drone_id: str, protocol: str, timestamp: float = None):
        """Record a detected pulse for a drone."""
        from protocol.drone_detector import DroneProtocol, default_detector
        import time
        ts = timestamp or time.time()
        proto = DroneProtocol(protocol)
        drone = default_detector.record_pulse(drone_id, ts, proto)
        return {
            "id": drone.drone_id,
            "pulse_count": drone.pulse_count,
            "confidence": round(drone.confidence, 3),
            "confirmed": drone.is_confirmed,
        }

    @app.post("/api/protocol/simulate")
    async def protocol_simulate_detection(protocol: str = "dji_ocusync", count: int = 10):
        """Simulate drone detection for testing."""
        from protocol.drone_detector import DroneProtocol, default_detector
        import time
        proto = DroneProtocol(protocol)
        drone_id = f"sim_{proto.value}_{int(time.time())}"
        
        # Simulate pulses
        interval = 0.01 if proto in (DroneProtocol.DJI_OCUSYNC, DroneProtocol.DJI_LIGHTBRIDGE) else 0.012
        for i in range(count):
            default_detector.record_pulse(drone_id, time.time() + i * interval, proto)
        
        return {
            "simulated": drone_id,
            "protocol": proto.value,
            "pulses": count,
        }

    # ========== FLIGHT LOG ANALYSIS ==========

    @app.post("/api/flightlogs/parse")
    async def flightlogs_parse(file_path: str):
        """Parse a flight log file."""
        from protocol.flight_log_parser import parse_flight_log
        try:
            log_data = parse_flight_log(file_path)
            return {
                "format": log_data.format.value,
                "header": {
                    "drone_model": log_data.header.drone_model,
                    "start_time": log_data.header.start_time.isoformat(),
                    "total_duration_s": log_data.header.total_duration_s,
                    "max_altitude_m": log_data.header.max_altitude_m,
                },
                "stats": {
                    "points": len(log_data.points),
                    "duration_s": log_data.duration_s,
                    "distance_m": round(log_data.total_distance_m, 2),
                    "avg_speed_mps": round(log_data.avg_speed_mps, 2),
                    "max_speed_mps": round(log_data.max_speed_mps, 2),
                },
            }
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/flightlogs/import")
    async def flightlogs_import(file_path: str):
        """Import flight log to database."""
        from protocol.flight_log_parser import parse_flight_log
        from skycore.storage import FlightDatabase
        if not db_path:
            return {"error": "no db configured"}
        try:
            log_data = parse_flight_log(file_path)
            with FlightDatabase(db_path) as fdb:
                for point in log_data.points:
                    fdb.insert_telemetry(
                        lat=point.lat, lon=point.lon, alt=point.altitude_m,
                        speed=point.speed_mps, battery=point.battery_percent
                    )
            return {"success": True, "points": len(log_data.points)}
        except Exception as e:
            return {"error": str(e)}

    # ========== EMERGENCY LANDING PLANNER ==========

    @app.get("/api/emergency/plan")
    async def emergency_plan(lat: float, lon: float, alt: float, reason: str = "unknown"):
        """Plan emergency landing based on current position."""
        from skycore.core.types import GeoPoint
        from skycore.navigation.landing import plan_emergency_landing
        
        try:
            current = GeoPoint(lat, lon, alt)
            plan = plan_emergency_landing(current, reason)
            return plan
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/emergency/safe-zones")
    async def emergency_safe_zones(lat: float, lon: float, radius_km: float = 5.0):
        """Find safe landing zones within radius."""
        # This would use terrain/airspace data
        return {
            "zones": [
                {"lat": lat + 0.01, "lon": lon + 0.01, "type": "park", "safe": True},
                {"lat": lat - 0.005, "lon": lon + 0.005, "type": "open_field", "safe": True},
            ],
            "radius_km": radius_km,
        }

    # ========== ORIGINAL ENDPOINTS ==========

    @app.get("/api/storage/stats")
    async def storage_stats():
        """Get flight database statistics."""
        if not db_path:
            return {"note": "no db configured"}
        from skycore.storage import FlightDatabase
        try:
            with FlightDatabase(db_path) as fdb:
                return fdb.stats()
        except Exception as e:
            return {"error": str(e)}

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
