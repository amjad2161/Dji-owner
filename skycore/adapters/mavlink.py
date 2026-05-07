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
from datetime import datetime
from typing import AsyncIterator, Optional

from skycore.core.drone import Drone
from skycore.core.types import FlightMode, GeoPoint, Telemetry

log = logging.getLogger(__name__)


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

    async def disconnect(self) -> None:
        # MAVSDK has no explicit close; just drop the system reference
        self._connected = False
        self._system = None

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
        async for pos in self._system.telemetry.position():
            async for batt in self._system.telemetry.battery():
                async for att in self._system.telemetry.attitude_euler():
                    return Telemetry(
                        timestamp=datetime.utcnow(),
                        position=GeoPoint(pos.latitude_deg, pos.longitude_deg, pos.relative_altitude_m),
                        velocity_xyz=(0.0, 0.0, 0.0),
                        yaw_deg=att.yaw_deg,
                        pitch_deg=att.pitch_deg,
                        roll_deg=att.roll_deg,
                        battery_percent=batt.remaining_percent * 100.0,
                        battery_voltage=batt.voltage_v,
                        gps_satellites=0,
                        gimbal_pitch_deg=0.0,
                        flight_mode=FlightMode.MISSION,
                    )
        raise RuntimeError("unreachable")

    async def telemetry_stream(self) -> AsyncIterator[Telemetry]:
        async for pos in self._system.telemetry.position():
            yield Telemetry(
                timestamp=datetime.utcnow(),
                position=GeoPoint(pos.latitude_deg, pos.longitude_deg, pos.relative_altitude_m),
                velocity_xyz=(0.0, 0.0, 0.0),
                yaw_deg=0.0,
                pitch_deg=0.0,
                roll_deg=0.0,
                battery_percent=0.0,
                battery_voltage=0.0,
                gps_satellites=0,
                gimbal_pitch_deg=0.0,
                flight_mode=FlightMode.MISSION,
            )
