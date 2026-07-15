"""In-process simulator. Realistic enough for development and tests.

The simulator implements the full Drone contract with simple kinematics:
straight-line motion toward a target at a configured speed, altitude
climb/descent at the same speed, battery drain proportional to motor work.
It does not model wind, IMU drift, or physical inertia — you wouldn't tune
PID gains against this, but you can develop and test missions, vision
pipelines, and the API stack against it.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from skycore.core.drone import Drone
from skycore.core.types import FlightMode, FlightStatus, GeoPoint, Telemetry

log = logging.getLogger(__name__)


class SimulatorDrone(Drone):
    """In-process simulated drone."""

    name = "simulator"

    def __init__(
        self,
        home: Optional[GeoPoint] = None,
        tick_hz: float = 10.0,
        battery_drain_per_sec: float = 0.02,
    ):
        self.home = home or GeoPoint(37.7749, -122.4194, 0.0)
        self.position = GeoPoint(self.home.lat, self.home.lon, 0.0)
        self.target_position: Optional[GeoPoint] = None
        self.target_speed_mps = 5.0
        self.velocity_xyz = (0.0, 0.0, 0.0)
        self.yaw_deg = 0.0
        self.gimbal_pitch_deg = 0.0
        self.battery_percent = 100.0
        self.battery_voltage = 17.4
        self.flight_mode = FlightMode.GROUND
        self.status = FlightStatus.DISCONNECTED
        self._connected = False
        self._tick_dt = 1.0 / tick_hz
        self._loop_task: Optional[asyncio.Task] = None
        self._recording = False
        self._battery_drain = battery_drain_per_sec
        self._photo_count = 0

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        if self._connected:
            return
        await asyncio.sleep(0.05)
        self._connected = True
        self.status = FlightStatus.CONNECTED
        self._loop_task = asyncio.create_task(self._physics_loop())
        log.info("Simulator connected at home=%s", self.home)

    async def disconnect(self) -> None:
        self._connected = False
        self.status = FlightStatus.DISCONNECTED
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except (asyncio.CancelledError, Exception):
                pass

    async def takeoff(self, altitude_m: float = 5.0) -> None:
        self.flight_mode = FlightMode.TAKEOFF
        self.status = FlightStatus.FLYING
        self.target_position = GeoPoint(self.position.lat, self.position.lon, altitude_m)
        await self._wait_until_at(self.target_position, tolerance_m=0.5)
        self.flight_mode = FlightMode.HOVER

    async def land(self) -> None:
        self.flight_mode = FlightMode.LANDING
        self.target_position = GeoPoint(self.position.lat, self.position.lon, 0.0)
        await self._wait_until_at(self.target_position, tolerance_m=0.3)
        self.flight_mode = FlightMode.GROUND
        self.status = FlightStatus.LANDED

    async def return_to_home(self) -> None:
        self.flight_mode = FlightMode.RTH
        safe_alt = max(self.position.alt, 30.0)
        self.target_position = GeoPoint(self.position.lat, self.position.lon, safe_alt)
        await self._wait_until_at(self.target_position, tolerance_m=1.0)
        self.target_position = GeoPoint(self.home.lat, self.home.lon, safe_alt)
        await self._wait_until_at(self.target_position, tolerance_m=1.0)
        await self.land()

    async def goto(self, point: GeoPoint, speed_mps: float = 5.0) -> None:
        self.target_speed_mps = speed_mps
        self.target_position = point
        self.flight_mode = FlightMode.MISSION
        await self._wait_until_at(point, tolerance_m=0.5)

    async def set_velocity(self, vx: float, vy: float, vz: float, yaw_rate: float = 0.0) -> None:
        self.flight_mode = FlightMode.POSITION
        self.target_position = None
        self.velocity_xyz = (vx, vy, vz)
        # NOTE: simplified — yaw_rate not integrated in this simulator

    async def set_yaw(self, yaw_deg: float) -> None:
        self.yaw_deg = yaw_deg % 360

    async def set_gimbal(self, pitch_deg: float) -> None:
        self.gimbal_pitch_deg = max(-90.0, min(30.0, pitch_deg))

    async def take_photo(self) -> str:
        await asyncio.sleep(0.05)
        self._photo_count += 1
        return f"sim://photo/{self._photo_count:05d}.jpg"

    async def start_recording(self) -> None:
        self._recording = True

    async def stop_recording(self) -> None:
        self._recording = False

    async def get_telemetry(self) -> Telemetry:
        return Telemetry(
            timestamp=datetime.now(timezone.utc),
            position=self.position,
            velocity_xyz=self.velocity_xyz,
            yaw_deg=self.yaw_deg,
            pitch_deg=0.0,
            roll_deg=0.0,
            battery_percent=self.battery_percent,
            battery_voltage=self.battery_voltage,
            gps_satellites=18,
            gimbal_pitch_deg=self.gimbal_pitch_deg,
            flight_mode=self.flight_mode,
            home=self.home,
            motor_rpm=(6000.0, 6005.0, 6010.0, 5995.0),
            signal_strength=100,
        )

    async def telemetry_stream(self) -> AsyncIterator[Telemetry]:
        while self._connected:
            yield await self.get_telemetry()
            await asyncio.sleep(self._tick_dt)

    # --- internal physics ---

    async def _physics_loop(self) -> None:
        try:
            while self._connected:
                self._step()
                await asyncio.sleep(self._tick_dt)
        except asyncio.CancelledError:
            return

    def _step(self) -> None:
        if self.target_position is not None:
            v = self.target_speed_mps
            dist_h = self.position.haversine_m(self.target_position)
            dist_v = self.target_position.alt - self.position.alt

            move_h = min(v * self._tick_dt, dist_h)
            if dist_h > 0.05:
                bearing = self.position.bearing_to(self.target_position)
                new_pos = self.position.offset_m(move_h, bearing)
            else:
                new_pos = self.position

            move_v_max = v * self._tick_dt
            move_v = max(-move_v_max, min(move_v_max, dist_v))
            self.position = GeoPoint(new_pos.lat, new_pos.lon, self.position.alt + move_v)
        elif self.velocity_xyz != (0.0, 0.0, 0.0):
            vx, vy, vz = self.velocity_xyz
            dx = vx * self._tick_dt  # forward
            dy = vy * self._tick_dt  # right
            dz = vz * self._tick_dt  # down
            # forward = at current yaw
            forward_bearing = self.yaw_deg
            right_bearing = (self.yaw_deg + 90) % 360
            new_pos = self.position.offset_m(dx, forward_bearing)
            new_pos = new_pos.offset_m(dy, right_bearing)
            self.position = GeoPoint(new_pos.lat, new_pos.lon, max(0, self.position.alt - dz))

        # Battery drain
        rate = 0.0005 if self.flight_mode == FlightMode.GROUND else self._battery_drain
        self.battery_percent = max(0.0, self.battery_percent - rate)
        self.battery_voltage = 14.0 + (self.battery_percent / 100.0) * 3.4

    async def _wait_until_at(self, point: GeoPoint, tolerance_m: float = 1.0, timeout_s: float = 300.0) -> None:
        elapsed = 0.0
        while elapsed < timeout_s:
            d_h = self.position.haversine_m(point)
            d_v = abs(self.position.alt - point.alt)
            if d_h < tolerance_m and d_v < tolerance_m:
                return
            await asyncio.sleep(self._tick_dt)
            elapsed += self._tick_dt
        raise TimeoutError(f"Did not reach {point} within {timeout_s}s (current={self.position})")
