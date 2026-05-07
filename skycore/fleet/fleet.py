"""Multi-drone coordination.

Run missions across a fleet of drones, with synchronized execution or
formation-flight patterns. The fleet is platform-agnostic — mix simulator,
Tello, MAVLink, and DJI bridge drones in the same group.
"""
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from typing import Sequence

from skycore.core.drone import Drone
from skycore.core.types import GeoPoint, MissionStep
from skycore.missions.waypoint import WaypointMission

log = logging.getLogger(__name__)


@dataclass
class FormationOffset:
    """Offset from leader in body frame, meters."""

    forward: float = 0.0
    right: float = 0.0
    down: float = 0.0


def line_formation(n: int, spacing_m: float = 5.0) -> list[FormationOffset]:
    """Side-by-side line, leader in middle."""
    return [FormationOffset(right=(i - (n - 1) / 2) * spacing_m) for i in range(n)]


def v_formation(n: int, spacing_m: float = 5.0, angle_deg: float = 45.0) -> list[FormationOffset]:
    """V-shape, leader at front."""
    offsets = [FormationOffset()]
    for i in range(1, n):
        side = (-1) ** i
        idx = (i + 1) // 2
        offsets.append(
            FormationOffset(
                forward=-idx * spacing_m * math.cos(math.radians(angle_deg)),
                right=side * idx * spacing_m * math.sin(math.radians(angle_deg)),
            )
        )
    return offsets


class Fleet:
    """Coordinator for a group of drones."""

    def __init__(self, drones: Sequence[Drone]):
        if not drones:
            raise ValueError("Fleet needs at least one drone")
        self.drones = list(drones)

    @property
    def leader(self) -> Drone:
        return self.drones[0]

    async def connect_all(self) -> None:
        await asyncio.gather(*(d.connect() for d in self.drones))

    async def disconnect_all(self) -> None:
        await asyncio.gather(*(d.disconnect() for d in self.drones))

    async def takeoff_all(self, altitude_m: float = 5.0) -> None:
        await asyncio.gather(*(d.takeoff(altitude_m) for d in self.drones))

    async def land_all(self) -> None:
        await asyncio.gather(*(d.land() for d in self.drones))

    async def execute_synchronized(self, mission: WaypointMission) -> None:
        """Every drone runs the identical mission in parallel."""
        await asyncio.gather(*(mission.execute(d) for d in self.drones))

    async def execute_in_formation(
        self,
        mission: WaypointMission,
        offsets: list[FormationOffset],
    ) -> None:
        """Leader runs mission; followers track at offsets."""
        if len(offsets) != len(self.drones):
            raise ValueError("offsets length must match number of drones")

        async def run_with_offset(d: Drone, off: FormationOffset) -> None:
            shifted = WaypointMission(name=f"{mission.name}-{d.name}")
            for step in mission.steps:
                yaw = step.yaw_deg or 0.0
                lat_off = (
                    off.forward * math.cos(math.radians(yaw))
                    - off.right * math.sin(math.radians(yaw))
                ) / 111_000.0
                lon_off = (
                    off.forward * math.sin(math.radians(yaw))
                    + off.right * math.cos(math.radians(yaw))
                ) / (111_000.0 * max(0.05, math.cos(math.radians(step.target.lat))))
                new_target = GeoPoint(
                    step.target.lat + lat_off,
                    step.target.lon + lon_off,
                    step.target.alt - off.down,
                )
                shifted.append(
                    MissionStep(
                        target=new_target,
                        speed_mps=step.speed_mps,
                        yaw_deg=step.yaw_deg,
                        gimbal_pitch_deg=step.gimbal_pitch_deg,
                        actions=step.actions,
                        hold_seconds=step.hold_seconds,
                    )
                )
            await shifted.execute(d)

        await asyncio.gather(*(run_with_offset(d, off) for d, off in zip(self.drones, offsets)))
