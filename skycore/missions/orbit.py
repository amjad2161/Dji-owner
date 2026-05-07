"""Generate orbit (point-of-interest) missions."""
from __future__ import annotations

from typing import Optional

from skycore.core.types import GeoPoint, MissionStep
from skycore.missions.waypoint import WaypointMission


def orbit_mission(
    center: GeoPoint,
    radius_m: float = 50.0,
    altitude_m: float = 30.0,
    waypoints: int = 12,
    speed_mps: float = 4.0,
    gimbal_pitch_deg: float = -30.0,
    photo_each: bool = True,
    name: Optional[str] = None,
) -> WaypointMission:
    """Generate a circular orbit around a point of interest.

    The drone always faces the POI; the gimbal is tilted down by
    gimbal_pitch_deg degrees.
    """
    if waypoints < 3:
        raise ValueError("At least 3 waypoints needed for an orbit")

    mission = WaypointMission(name=name or f"orbit-{int(radius_m)}m")
    for i in range(waypoints):
        bearing = (360.0 / waypoints) * i
        wp = center.offset_m(radius_m, bearing, alt_delta=altitude_m - center.alt)
        # Heading from waypoint back to POI
        yaw = wp.bearing_to(center)
        mission.append(
            MissionStep(
                target=wp,
                speed_mps=speed_mps,
                yaw_deg=yaw,
                gimbal_pitch_deg=gimbal_pitch_deg,
                actions=["take_photo"] if photo_each else [],
            )
        )
    return mission
