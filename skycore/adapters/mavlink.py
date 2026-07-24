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
from datetime import datetime, timezone
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
        # Latest telemetry components, kept fresh by background subscription pumps.
        # Battery defaults to 100% so a SafeDrone monitor does NOT read 0% (and trigger
        # an emergency land) before the first real battery frame arrives.
        self._batt_pct = 100.0
        self._batt_v = 0.0
        self._gps_sats = 0
        self._att = (0.0, 0.0, 0.0)   # yaw, pitch, roll (deg)
        self._ground_amsl: Optional[float] = None   # takeoff-ground AMSL, for AGL->AMSL goto
        self._sub_tasks: list = []

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
        # keep the latest battery / GPS / attitude cached for telemetry + safety
        self._sub_tasks = [
            asyncio.create_task(self._pump_battery()),
            asyncio.create_task(self._pump_gps()),
            asyncio.create_task(self._pump_attitude()),
            asyncio.create_task(self._pump_position_amsl()),
        ]

    async def disconnect(self) -> None:
        for t in self._sub_tasks:
            t.cancel()
        self._sub_tasks = []
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
        # GeoPoint.alt is height above takeoff (AGL); goto_location wants absolute AMSL.
        # Convert using the takeoff-ground AMSL so a mission planned at e.g. 30 m AGL from
        # a 400 m-elevation site does NOT command a descent to 30 m AMSL (into terrain).
        await self._system.action.set_maximum_speed(speed_mps)
        ground_amsl = self._ground_amsl
        if ground_amsl is None:
            async for pos in self._system.telemetry.position():
                ground_amsl = pos.absolute_altitude_m - pos.relative_altitude_m
                break
        await self._system.action.goto_location(
            point.lat, point.lon, (ground_amsl or 0.0) + point.alt, 0.0
        )

    async def set_velocity(self, vx: float, vy: float, vz: float, yaw_rate: float = 0.0) -> None:
        from mavsdk.offboard import VelocityBodyYawspeed
        await self._system.offboard.set_velocity_body(
            VelocityBodyYawspeed(vx, vy, vz, yaw_rate)
        )
        try:
            await self._system.offboard.start()
        except Exception as e:
            # start() raises when offboard is already active; log anything else so a real
            # failure (mode refused, not armed) is not silently swallowed.
            if "ALREADY" not in str(e).upper():
                log.warning("offboard start failed: %s", e)

    async def set_yaw(self, yaw_deg: float) -> None:
        # Action API does not expose yaw directly; use offboard attitude instead
        log.debug("set_yaw not directly supported by MAVSDK action API")

    async def set_gimbal(self, pitch_deg: float) -> None:
        try:
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

    # --- telemetry component pumps (keep the latest reading cached) ---

    async def _pump_battery(self) -> None:
        try:
            async for b in self._system.telemetry.battery():
                self._batt_pct = b.remaining_percent * 100.0
                self._batt_v = b.voltage_v
        except (asyncio.CancelledError, Exception):
            return

    async def _pump_gps(self) -> None:
        try:
            async for g in self._system.telemetry.gps_info():
                self._gps_sats = g.num_satellites
        except (asyncio.CancelledError, Exception):
            return

    async def _pump_attitude(self) -> None:
        try:
            async for a in self._system.telemetry.attitude_euler():
                self._att = (a.yaw_deg, a.pitch_deg, a.roll_deg)
        except (asyncio.CancelledError, Exception):
            return

    async def _pump_position_amsl(self) -> None:
        try:
            async for pos in self._system.telemetry.position():
                self._ground_amsl = pos.absolute_altitude_m - pos.relative_altitude_m
        except (asyncio.CancelledError, Exception):
            return

    def _frame(self, pos) -> Telemetry:
        yaw, pitch, roll = self._att
        return Telemetry(
            timestamp=datetime.now(timezone.utc),
            position=GeoPoint(pos.latitude_deg, pos.longitude_deg, pos.relative_altitude_m),
            velocity_xyz=(0.0, 0.0, 0.0),
            yaw_deg=yaw,
            pitch_deg=pitch,
            roll_deg=roll,
            battery_percent=self._batt_pct,
            battery_voltage=self._batt_v,
            gps_satellites=self._gps_sats,
            gimbal_pitch_deg=0.0,
            flight_mode=FlightMode.MISSION,
        )

    async def get_telemetry(self) -> Telemetry:
        async for pos in self._system.telemetry.position():
            return self._frame(pos)
        raise RuntimeError("unreachable")

    async def telemetry_stream(self) -> AsyncIterator[Telemetry]:
        async for pos in self._system.telemetry.position():
            yield self._frame(pos)
