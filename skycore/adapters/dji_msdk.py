"""DJI Mobile SDK V5 bridge adapter.

The DJI MSDK runs on Android, not on the host where SkyCore lives. To
integrate, this adapter speaks to a small Android "bridge app" running on a
phone connected to the DJI RC. The bridge app is a thin wrapper that
exposes MSDK calls over WebSocket.

The bridge app source lives in `bridge/android/` (build with Android Studio).
This Python adapter speaks the bridge JSON protocol.

Protocol summary (over WebSocket):
    → {"cmd": "connect"}
    → {"cmd": "takeoff", "altitude": 5.0}
    → {"cmd": "goto", "lat": 37.7, "lon": -122.4, "alt": 30, "speed": 5}
    ← {"event": "telemetry", "data": { ...Telemetry... }}

This adapter focuses on the message protocol; the heavy lifting (actual
MSDK invocations) lives in the Android bridge.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncIterator, Optional

from skycore.core.drone import Drone
from skycore.core.types import FlightMode, GeoPoint, Telemetry

log = logging.getLogger(__name__)


class DjiBridgeDrone(Drone):
    name = "dji-bridge"

    def __init__(self, bridge_url: str = "ws://192.168.1.100:8765"):
        try:
            import websockets  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "websockets is required for the DJI bridge. Install with: pip install websockets"
            ) from e
        self._bridge_url = bridge_url
        self._ws = None
        self._connected = False
        self._latest: Optional[Telemetry] = None
        self._tm_listeners: list[asyncio.Queue] = []
        self._reader_task: Optional[asyncio.Task] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        import websockets
        self._ws = await websockets.connect(self._bridge_url)
        await self._send({"cmd": "connect"})
        self._connected = True
        self._reader_task = asyncio.create_task(self._reader())
        log.info("Connected to DJI bridge at %s", self._bridge_url)

    async def disconnect(self) -> None:
        self._connected = False
        if self._reader_task:
            self._reader_task.cancel()
        if self._ws:
            await self._ws.close()

    async def takeoff(self, altitude_m: float = 5.0) -> None:
        await self._send({"cmd": "takeoff", "altitude": altitude_m})

    async def land(self) -> None:
        await self._send({"cmd": "land"})

    async def return_to_home(self) -> None:
        await self._send({"cmd": "rth"})

    async def goto(self, point: GeoPoint, speed_mps: float = 5.0) -> None:
        await self._send(
            {"cmd": "goto", "lat": point.lat, "lon": point.lon, "alt": point.alt, "speed": speed_mps}
        )

    async def set_velocity(self, vx: float, vy: float, vz: float, yaw_rate: float = 0.0) -> None:
        await self._send({"cmd": "velocity", "vx": vx, "vy": vy, "vz": vz, "yaw_rate": yaw_rate})

    async def set_yaw(self, yaw_deg: float) -> None:
        await self._send({"cmd": "yaw", "deg": yaw_deg})

    async def set_gimbal(self, pitch_deg: float) -> None:
        await self._send({"cmd": "gimbal", "pitch": pitch_deg})

    async def take_photo(self) -> str:
        await self._send({"cmd": "photo"})
        return "dji://photo/last"

    async def start_recording(self) -> None:
        await self._send({"cmd": "record_start"})

    async def stop_recording(self) -> None:
        await self._send({"cmd": "record_stop"})

    async def get_telemetry(self) -> Telemetry:
        if self._latest is None:
            await asyncio.sleep(0.5)
        if self._latest is None:
            raise RuntimeError("No telemetry received from bridge yet")
        return self._latest

    async def telemetry_stream(self) -> AsyncIterator[Telemetry]:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._tm_listeners.append(q)
        try:
            while self._connected:
                yield await q.get()
        finally:
            self._tm_listeners.remove(q)

    # --- internal ---

    async def _send(self, msg: dict) -> None:
        if not self._ws:
            raise RuntimeError("Not connected to bridge")
        await self._ws.send(json.dumps(msg))

    async def _reader(self) -> None:
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                if msg.get("event") == "telemetry":
                    self._latest = self._parse_telemetry(msg.get("data", {}))
                    for q in self._tm_listeners:
                        try:
                            q.put_nowait(self._latest)
                        except asyncio.QueueFull:
                            pass
        except asyncio.CancelledError:
            return

    def _parse_telemetry(self, d: dict) -> Telemetry:
        return Telemetry(
            timestamp=datetime.utcnow(),
            position=GeoPoint(d.get("lat", 0), d.get("lon", 0), d.get("alt", 0)),
            velocity_xyz=tuple(d.get("vel", (0, 0, 0))),
            yaw_deg=d.get("yaw", 0.0),
            pitch_deg=d.get("pitch", 0.0),
            roll_deg=d.get("roll", 0.0),
            battery_percent=d.get("battery_percent", 0.0),
            battery_voltage=d.get("battery_voltage", 0.0),
            gps_satellites=d.get("gps_sats", 0),
            gimbal_pitch_deg=d.get("gimbal_pitch", 0.0),
            flight_mode=FlightMode(d.get("mode", "hover")),
        )
