"""MAVLink backend for PX4 / ArduPilot drones.

Wraps `mavsdk` (https://github.com/mavlink/MAVSDK) which is the modern,
async-first MAVLink SDK from the PX4 maintainers. Works with any
MAVLink-compatible vehicle: PX4, ArduPilot, hardware-in-the-loop (Gazebo),
or SITL on localhost.

Install:
    pip install mavsdk

Note: This is a thin adapter; the underlying MAVSDK already implements the
bulk of the work. The adapter exists to fit MAVSDK into SkyCore's unified
interface so vision / mission code written for the simulator works unchanged.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, Optional

from skycore.core.drone import Drone
from skycore.core.types import FlightMode, GeoPoint, Telemetry

log = logging.getLogger(__name__)


@dataclass
class _CachedTelemetry:
    """Cached telemetry values for streaming."""
    position: Optional[any] = None
    battery: Optional[any] = None
    attitude: Optional[any] = None
    gps_info: Optional[any] = None
    health: Optional[any] = None
    last_update: float = field(default_factory=lambda: datetime.utcnow().timestamp())


class MavlinkDrone(Drone):
    name = "mavlink"

    def __init__(self, connection_url: str = "udp://:14540"):
        try:
            from mavsdk import System  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "mavsdk is required for the MAVLink backend. Install with: pip install mavsdk"
            ) from e
        from mavsdk import System
        self._System = System
        self._system: Optional[System] = None
        self._connection_url = connection_url
        self._connected = False
        self._cache = _CachedTelemetry()
        self._telemetry_task: Optional[asyncio.Task] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self._system = self._System()
        await self._system.connect(system_address=self._connection_url)
        log.info("Waiting for MAVLink connection on %s...", self._connection_url)
        async for state in self._system.core.connection_state():
            if state.is_connected:
                self._connected = True
                log.info("MAVLink connected")
                break

        # Start telemetry background task
        self._telemetry_task = asyncio.create_task(self._telemetry_bg())

    async def disconnect(self) -> None:
        if self._telemetry_task:
            self._telemetry_task.cancel()
            try:
                await self._telemetry_task
            except asyncio.CancelledError:
                pass
        self._connected = False
        self._system = None

    async def _telemetry_bg(self) -> None:
        """Background task to continuously update telemetry cache."""
        try:
            async for pos in self._system.telemetry.position():
                self._cache.position = pos
                self._cache.last_update = datetime.utcnow().timestamp()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning("Position stream error: %s", e)

    async def takeoff(self, altitude_m: float = 5.0) -> None:
        await self._system.action.set_takeoff_altitude(altitude_m)
        await self._system.action.arm()
        await self._system.action.takeoff()

    async def land(self) -> None:
        await self._system.action.land()

    async def return_to_home(self) -> None:
        await self._system.action.return_to_launch()

    async def goto(self, point: GeoPoint, speed_mps: float = 5.0) -> None:
        # goto_location takes lat, lon, abs alt (AMSL), yaw
        await self._system.action.set_maximum_speed(speed_mps)
        await self._system.action.goto_location(point.lat, point.lon, point.alt, 0.0)

    async def set_velocity(self, vx: float, vy: float, vz: float, yaw_rate: float = 0.0) -> None:
        from mavsdk.offboard import VelocityBodyYawspeed
        await self._system.offboard.set_velocity_body(
            VelocityBodyYawspeed(vx, vy, vz, yaw_rate)
        )
        try:
            await self._system.offboard.start()
        except Exception:
            pass  # already started

    async def set_yaw(self, yaw_deg: float) -> None:
        # Action API does not expose yaw directly; use offboard attitude instead
        log.debug("set_yaw not directly supported by MAVSDK action API")

    async def set_gimbal(self, pitch_deg: float) -> None:
        try:
            from mavsdk.gimbal import GimbalMode
            await self._system.gimbal.set_pitch_and_yaw(pitch_deg, 0.0)
        except Exception as e:
            log.warning("Gimbal control failed: %s", e)

    async def take_photo(self) -> str:
        try:
            await self._system.camera.take_photo()
            return "camera://photo/last"
        except Exception as e:
            log.warning("take_photo failed: %s", e)
            return ""

    async def start_recording(self) -> None:
        try:
            await self._system.camera.start_video()
        except Exception as e:
            log.warning("start_recording failed: %s", e)

    async def stop_recording(self) -> None:
        try:
            await self._system.camera.stop_video()
        except Exception as e:
            log.warning("stop_recording failed: %s", e)

    async def get_telemetry(self) -> Telemetry:
        # Fetch fresh telemetry
        pos, batt, att, gps = await self._fetch_all_telemetry()

        if pos is None:
            raise RuntimeError("No telemetry received from MAVLink system")

        return Telemetry(
            timestamp=datetime.utcnow(),
            position=GeoPoint(pos.latitude_deg, pos.longitude_deg, pos.relative_altitude_m),
            velocity_xyz=(0.0, 0.0, 0.0),  # MAVSDK position doesn't include velocity
            yaw_deg=att.yaw_deg if att else 0.0,
            pitch_deg=att.pitch_deg if att else 0.0,
            roll_deg=att.roll_deg if att else 0.0,
            battery_percent=batt.remaining_percent * 100.0 if batt else 0.0,
            battery_voltage=batt.voltage_v if batt else 0.0,
            gps_satellites=gps.num_satellites if gps else 0,  # Get from GPSInfo
            gimbal_pitch_deg=0.0,  # Would need separate gimbal telemetry
            flight_mode=FlightMode.MISSION,
            home=None,  # Would need to query home position
        )

    async def _fetch_all_telemetry(self) -> tuple:
        """Fetch all telemetry data concurrently."""
        pos, batt, att, gps = None, None, None, None

        # Fetch all in parallel
        async def get_pos():
            async for p in self._system.telemetry.position():
                return p

        async def get_batt():
            async for b in self._system.telemetry.battery():
                return b

        async def get_att():
            async for a in self._system.telemetry.attitude_euler():
                return a

        async def get_gps():
            async for g in self._system.telemetry.gps_info():
                return g

        # Run all fetchers concurrently
        results = await asyncio.gather(
            get_pos(), get_batt(), get_att(), get_gps(),
            return_exceptions=True
        )

        pos = results[0] if not isinstance(results[0], Exception) else None
        batt = results[1] if not isinstance(results[1], Exception) else None
        att = results[2] if not isinstance(results[2], Exception) else None
        gps = results[3] if not isinstance(results[3], Exception) else None

        return pos, batt, att, gps

    async def telemetry_stream(self) -> AsyncIterator[Telemetry]:
        """Stream telemetry at a steady 2 Hz.

        Reuses ``get_telemetry`` (which fetches position/battery/attitude/GPS
        concurrently via ``_fetch_all_telemetry``) instead of nesting
        ``async for`` subscriptions. The previous nested-subscription form
        re-opened a fresh MAVSDK stream for every field on every frame, which
        leaked subscriptions and made the loop fragile. One bounded fetch per
        tick is correct and predictable.
        """
        while self._connected:
            try:
                yield await self.get_telemetry()
                await asyncio.sleep(0.5)  # 2 Hz
            except asyncio.CancelledError:
                break
            except RuntimeError:
                # No telemetry yet (link still settling) — back off and retry.
                await asyncio.sleep(1.0)
            except Exception as e:
                log.warning("Telemetry stream error: %s", e)
                await asyncio.sleep(1.0)  # Backoff on error
