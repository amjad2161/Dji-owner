"""Tello backend, wrapping djitellopy.

DJI Tello is the easiest real DJI hardware to integrate with: it speaks a
UDP text protocol over Wi-Fi, no SDK key required, and the open-source
`djitellopy` library exposes everything. This adapter maps the SkyCore
interface onto djitellopy's API.

Limitations vs. real Mavic drones:
- Tello has no GPS — position is estimated relative to takeoff in meters.
- No gimbal (camera is fixed pitch).
- 30 m max range. ~13 min flight time. 5 MP camera, 720p video.

Install:
    pip install djitellopy
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime
from typing import AsyncIterator, Optional

from skycore.core.drone import Drone
from skycore.core.types import FlightMode, FlightStatus, GeoPoint, Telemetry

log = logging.getLogger(__name__)


class TelloDrone(Drone):
    name = "tello"

    def __init__(self, home: Optional[GeoPoint] = None):
        try:
            from djitellopy import Tello  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "djitellopy is required for the Tello backend. Install with: pip install djitellopy"
            ) from e
        from djitellopy import Tello
        self._Tello = Tello
        self._tello: Optional[Tello] = None
        self.home = home or GeoPoint(0.0, 0.0, 0.0)
        self._connected = False
        # Tello has no GPS; we track an estimated position in meters from takeoff.
        self._x_m = 0.0
        self._y_m = 0.0
        self._z_m = 0.0
        self._yaw_deg = 0.0
        self._mode = FlightMode.GROUND

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        loop = asyncio.get_running_loop()
        self._tello = self._Tello()
        await loop.run_in_executor(None, self._tello.connect)
        self._connected = True
        log.info("Tello connected. battery=%s%%", self._tello.get_battery())

    async def disconnect(self) -> None:
        if self._tello and self._connected:
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(None, self._tello.end)
            except Exception:
                pass
        self._connected = False

    async def takeoff(self, altitude_m: float = 1.5) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._tello.takeoff)
        self._mode = FlightMode.HOVER
        if altitude_m > 1.5:
            await self.set_velocity(0, 0, -((altitude_m - 1.5) * 1.0), 0)
            await asyncio.sleep(altitude_m - 1.5)
            await self.set_velocity(0, 0, 0, 0)

    async def land(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._tello.land)
        self._mode = FlightMode.GROUND

    async def return_to_home(self) -> None:
        # Tello has no GPS RTH — emulate by flying back to (0,0) using internal odometry,
        # then land. Reasonable inside its 30 m range.
        await self.goto(GeoPoint(self.home.lat, self.home.lon, max(self._z_m, 1.5)))
        await self.land()

    async def goto(self, point: GeoPoint, speed_mps: float = 1.0) -> None:
        # Translate target to relative dx,dy,dz in meters. For Tello, lat/lon
        # work poorly because there's no GPS — we treat alt as Z and use the
        # provided home as origin.
        dx = (point.lat - self.home.lat) * 111000
        dy = (point.lon - self.home.lon) * 111000 * math.cos(math.radians(self.home.lat))
        dz = point.alt
        # Drive there with a simple proportional controller
        await asyncio.sleep(0.1)
        loop = asyncio.get_running_loop()
        # cm-precision
        await loop.run_in_executor(
            None,
            self._tello.go_xyz_speed,
            int((dx - self._x_m) * 100),
            int((dy - self._y_m) * 100),
            int((dz - self._z_m) * 100),
            max(10, min(100, int(speed_mps * 100))),
        )
        self._x_m, self._y_m, self._z_m = dx, dy, dz

    async def set_velocity(self, vx: float, vy: float, vz: float, yaw_rate: float = 0.0) -> None:
        loop = asyncio.get_running_loop()
        # Tello rc command takes left-right, fwd-back, up-down, yaw, all -100..100
        await loop.run_in_executor(
            None,
            self._tello.send_rc_control,
            int(max(-100, min(100, vy * 100))),
            int(max(-100, min(100, vx * 100))),
            int(max(-100, min(100, -vz * 100))),
            int(max(-100, min(100, yaw_rate))),
        )

    async def set_yaw(self, yaw_deg: float) -> None:
        delta = (yaw_deg - self._yaw_deg) % 360
        if delta > 180:
            delta -= 360
        loop = asyncio.get_running_loop()
        if delta > 0:
            await loop.run_in_executor(None, self._tello.rotate_clockwise, int(abs(delta)))
        else:
            await loop.run_in_executor(None, self._tello.rotate_counter_clockwise, int(abs(delta)))
        self._yaw_deg = yaw_deg % 360

    async def set_gimbal(self, pitch_deg: float) -> None:
        # Tello has no gimbal
        log.debug("Tello has no gimbal; ignoring set_gimbal(%s)", pitch_deg)

    async def take_photo(self) -> str:
        # Tello SDK does not expose a direct photo trigger — grab a frame from the video stream.
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._tello.streamon)
        await asyncio.sleep(0.5)
        frame = await loop.run_in_executor(None, self._tello.get_frame_read)
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        path = f"./tello-photo-{ts}.jpg"
        try:
            import cv2  # type: ignore
            cv2.imwrite(path, frame.frame)
        except ImportError:
            log.warning("opencv-python not installed; photo not saved")
        return path

    async def start_recording(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._tello.streamon)

    async def stop_recording(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._tello.streamoff)

    async def get_telemetry(self) -> Telemetry:
        loop = asyncio.get_running_loop()
        battery = await loop.run_in_executor(None, self._tello.get_battery)
        height = await loop.run_in_executor(None, self._tello.get_height)
        return Telemetry(
            timestamp=datetime.utcnow(),
            position=GeoPoint(self.home.lat, self.home.lon, height / 100.0),
            velocity_xyz=(0.0, 0.0, 0.0),
            yaw_deg=self._yaw_deg,
            pitch_deg=0.0,
            roll_deg=0.0,
            battery_percent=float(battery),
            battery_voltage=3.7,  # Tello reports percent, not voltage
            gps_satellites=0,
            gimbal_pitch_deg=0.0,
            flight_mode=self._mode,
            home=self.home,
        )

    async def telemetry_stream(self) -> AsyncIterator[Telemetry]:
        while self._connected:
            yield await self.get_telemetry()
            await asyncio.sleep(0.5)
