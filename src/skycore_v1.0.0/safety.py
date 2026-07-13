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
        self._safety_lock = asyncio.Lock()  # Prevent concurrent safety actions
        self._halt_event = asyncio.Event()   # Signal to halt motion

    @property
    def is_connected(self) -> bool:
        return self.inner.is_connected

    async def connect(self):
        await self.inner.connect()
        self._monitor_task = asyncio.create_task(self._monitor())

    async def disconnect(self):
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        await self.inner.disconnect()

    async def takeoff(self, altitude_m: float = 5.0):
        if altitude_m > self.config.max_altitude_m:
            raise SafetyError(f"Takeoff altitude {altitude_m} m exceeds geofence {self.config.max_altitude_m} m")
        # Reset safety state on new flight
        self._tripped = False
        self._halt_event.clear()
        await self.inner.takeoff(altitude_m)

    async def land(self):
        async with self._safety_lock:
            self._tripped = True
        await self.inner.land()

    async def return_to_home(self):
        async with self._safety_lock:
            self._tripped = True
        await self.inner.return_to_home()

    async def goto(self, point: GeoPoint, speed_mps: float = 5.0):
        # Check halt condition - GPS issues should prevent motion
        if self._halt_event.is_set():
            log.warning("Motion halted - GPS or safety issue detected")
            raise SafetyError("Motion halted - GPS unstable or safety triggered")
        
        self._check_geofence(point)
        await self.inner.goto(point, speed_mps)

    async def set_velocity(self, vx: float, vy: float, vz: float, yaw_rate: float = 0.0):
        if self._halt_event.is_set():
            log.warning("Velocity blocked - safety halted")
            raise SafetyError("Motion halted - awaiting GPS stabilization")
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
            if d > self.config.max_distance_m:
                raise SafetyError(
                    f"Target {d:.0f} m from home exceeds geofence radius {self.config.max_distance_m} m"
                )

    def reset(self) -> None:
        """Reset the safety layer after an incident (e.g., battery replaced)."""
        self._tripped = False
        self._halt_event.clear()

    async def _monitor(self) -> None:
        """Monitor telemetry and trigger safety actions when needed.
        
        Uses locks to prevent concurrent safety actions and Events to signal
        halt conditions without breaking the monitoring loop.
        """
        try:
            async for tm in self.inner.telemetry_stream():
                # Check battery land threshold
                if tm.battery_percent <= self.config.land_battery_threshold:
                    log.warning(
                        "Battery %.0f%% ≤ land threshold (%d%%); executing emergency land.",
                        tm.battery_percent,
                        self.config.land_battery_threshold,
                    )
                    async with self._safety_lock:
                        self._tripped = True
                    try:
                        await self.inner.land()
                    except Exception as e:
                        log.error("Emergency land failed: %s", e)
                    # Continue monitoring - drone may still report telemetry while landing

                # Check battery RTH threshold
                elif tm.battery_percent <= self.config.rth_battery_threshold:
                    log.warning(
                        "Battery %.0f%% ≤ RTH threshold (%d%%); returning to home.",
                        tm.battery_percent,
                        self.config.rth_battery_threshold,
                    )
                    async with self._safety_lock:
                        self._tripped = True
                    try:
                        await self.inner.return_to_home()
                    except Exception as e:
                        log.error("RTH failed: %s. Attempting land.", e)
                        try:
                            await self.inner.land()
                        except Exception as land_e:
                            log.error("Land also failed: %s", land_e)

                # Check GPS satellite count
                elif tm.gps_satellites < self.config.min_gps_satellites:
                    log.warning(
                        "GPS satellites %d below minimum (%d); halting motion.",
                        tm.gps_satellites,
                        self.config.min_gps_satellites,
                    )
                    # Signal halt - prevent further motion commands
                    self._halt_event.set()
                    try:
                        # Halt motion by setting zero velocity
                        await self.inner.set_velocity(0, 0, 0, 0)
                    except Exception as e:
                        log.warning("Failed to halt motion: %s", e)
                    # Don't break - keep monitoring for GPS recovery

                # GPS recovered - clear halt condition
                elif tm.gps_satellites >= self.config.min_gps_satellites and self._halt_event.is_set():
                    if tm.battery_percent > self.config.rth_battery_threshold:
                        log.info("GPS stabilized (%d sats) - clearing halt condition", tm.gps_satellites)
                        self._halt_event.clear()
                        self._tripped = False

        except asyncio.CancelledError:
            log.debug("Safety monitor cancelled")
        except Exception as e:
            log.error("Safety monitor error: %s", e)
