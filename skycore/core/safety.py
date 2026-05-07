"""Safety layer. Geofence, battery RTH, link-loss handling.

Wraps any Drone instance with safety guards. The safety wrapper exposes the
same interface as the underlying drone but intercepts dangerous operations
and triggers protective behavior (RTH, land) when limits are crossed.

Safety is enforced in software here — it is not a substitute for the drone's
built-in geofencing or for following local aviation regulations.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional

from skycore.core.drone import Drone
from skycore.core.types import GeofenceConfig, GeoPoint, Telemetry

log = logging.getLogger(__name__)


class SafetyError(RuntimeError):
    """Raised when a command would violate safety policy."""


class SafeDrone(Drone):
    """Wrap a drone with geofence and battery monitors."""

    def __init__(self, inner: Drone, config: GeofenceConfig):
        self.inner = inner
        self.config = config
        self.name = f"safe({inner.name})"
        self._monitor_task: Optional[asyncio.Task] = None
        self._tripped = False

    @property
    def is_connected(self) -> bool:
        return self.inner.is_connected

    async def connect(self):
        await self.inner.connect()
        self._monitor_task = asyncio.create_task(self._monitor())

    async def disconnect(self):
        if self._monitor_task:
            self._monitor_task.cancel()
        await self.inner.disconnect()

    async def takeoff(self, altitude_m: float = 5.0):
        if altitude_m > self.config.max_altitude_m:
            raise SafetyError(f"Takeoff altitude {altitude_m} m exceeds geofence {self.config.max_altitude_m} m")
        await self.inner.takeoff(altitude_m)

    async def land(self):
        await self.inner.land()

    async def return_to_home(self):
        await self.inner.return_to_home()

    async def goto(self, point: GeoPoint, speed_mps: float = 5.0):
        self._check_geofence(point)
        await self.inner.goto(point, speed_mps)

    async def set_velocity(self, vx: float, vy: float, vz: float, yaw_rate: float = 0.0):
        await self.inner.set_velocity(vx, vy, vz, yaw_rate)

    async def set_yaw(self, yaw_deg: float):
        await self.inner.set_yaw(yaw_deg)

    async def set_gimbal(self, pitch_deg: float):
        await self.inner.set_gimbal(pitch_deg)

    async def take_photo(self):
        return await self.inner.take_photo()

    async def start_recording(self):
        await self.inner.start_recording()

    async def stop_recording(self):
        await self.inner.stop_recording()

    async def get_telemetry(self):
        return await self.inner.get_telemetry()

    def telemetry_stream(self) -> AsyncIterator[Telemetry]:
        return self.inner.telemetry_stream()

    # --- internal ---

    def _check_geofence(self, point: GeoPoint) -> None:
        if point.alt > self.config.max_altitude_m:
            raise SafetyError(f"Target altitude {point.alt} m exceeds geofence {self.config.max_altitude_m} m")
        if self.config.home is not None:
            d = self.config.home.haversine_m(point)
            if d > self.config.max_radius_m:
                raise SafetyError(
                    f"Target {d:.0f} m from home exceeds geofence radius {self.config.max_radius_m} m"
                )

    async def _monitor(self):
        try:
            async for tm in self.inner.telemetry_stream():
                if self._tripped:
                    continue
                if tm.battery_percent <= self.config.land_battery_threshold:
                    log.warning("Battery %.0f%% ≤ land threshold; landing.", tm.battery_percent)
                    self._tripped = True
                    asyncio.create_task(self.inner.land())
                elif tm.battery_percent <= self.config.rth_battery_threshold:
                    log.warning("Battery %.0f%% ≤ RTH threshold; returning to home.", tm.battery_percent)
                    self._tripped = True
                    asyncio.create_task(self.inner.return_to_home())
                elif tm.gps_satellites < self.config.min_gps_satellites:
                    log.warning("GPS satellites %d below minimum; halting motion.", tm.gps_satellites)
        except asyncio.CancelledError:
            pass
