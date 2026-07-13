"""Generic waypoint-mission executor.

Works against any backend that implements `Drone`. The executor handles
yaw alignment between waypoints, gimbal positioning, hold times, and
actions (take_photo, start/stop_recording).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from skycore.core.drone import Drone
from skycore.core.types import GeoPoint, MissionStep

log = logging.getLogger(__name__)


@dataclass
class WaypointMission:
    steps: list[MissionStep] = field(default_factory=list)
    name: str = "unnamed"

    def __len__(self) -> int:
        return len(self.steps)

    def append(self, step: MissionStep) -> "WaypointMission":
        self.steps.append(step)
        return self

    async def execute(self, drone: Drone, takeoff_altitude_m: float = 5.0, return_after: bool = True) -> None:
        log.info("Executing mission '%s' (%d waypoints)", self.name, len(self))
        if not drone.is_connected:
            await drone.connect()

        await drone.takeoff(altitude_m=takeoff_altitude_m)

        for i, step in enumerate(self.steps):
            log.info("  [%d/%d] -> %s", i + 1, len(self), step.target)
            yaw = step.yaw_deg
            if yaw is None and i + 1 < len(self.steps):
                yaw = step.target.bearing_to(self.steps[i + 1].target)
            if yaw is not None:
                await drone.set_yaw(yaw)
            if step.gimbal_pitch_deg is not None:
                await drone.set_gimbal(step.gimbal_pitch_deg)

            await drone.goto(step.target, speed_mps=step.speed_mps)

            for action in step.actions:
                await self._do_action(drone, action)

            if step.hold_seconds > 0:
                await asyncio.sleep(step.hold_seconds)

        if return_after:
            log.info("  mission complete; returning to home")
            await drone.return_to_home()

    async def _do_action(self, drone: Drone, action: str) -> None:
        if action == "take_photo":
            uri = await drone.take_photo()
            log.info("     photo: %s", uri)
        elif action == "start_record":
            await drone.start_recording()
        elif action == "stop_record":
            await drone.stop_recording()
        else:
            log.warning("Unknown action: %s", action)
