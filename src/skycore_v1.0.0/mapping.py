"""Lawnmower / boustrophedon survey missions for mapping.

Generates the standard zig-zag pattern used for photogrammetry. The
output is compatible with OpenDroneMap or Pix4D — fly the mission, then
upload the photos to your processor of choice.
"""
from __future__ import annotations

from typing import Optional

from skycore.core.types import GeoPoint, MissionStep
from skycore.missions.waypoint import WaypointMission


def lawnmower_mission(
    sw_corner: GeoPoint,
    ne_corner: GeoPoint,
    altitude_m: float = 50.0,
    side_overlap: float = 0.65,
    front_overlap: float = 0.75,
    sensor_width_m_at_altitude: float = 70.0,  # ground footprint of the camera
    speed_mps: float = 4.0,
    gimbal_pitch_deg: float = -90.0,  # nadir for mapping
    name: Optional[str] = None,
) -> WaypointMission:
    """Generate a lawnmower mission covering the bounding box.

    sw_corner: south-west corner (lower-left in EPSG:4326)
    ne_corner: north-east corner (upper-right)
    altitude_m: flying altitude AGL
    sensor_width_m_at_altitude: width of camera footprint on the ground
        (e.g. for a Mavic 3 with 84° FoV at 50 m AGL, footprint ≈ 90 m)
    """
    if sw_corner.lat >= ne_corner.lat or sw_corner.lon >= ne_corner.lon:
        raise ValueError("sw_corner must be south-west of ne_corner")

    line_spacing_m = sensor_width_m_at_altitude * (1 - side_overlap)
    if line_spacing_m <= 0:
        raise ValueError("side_overlap too high")

    mission = WaypointMission(name=name or "survey")

    # We'll fly east-west lines, stepping north each time.
    sw = GeoPoint(sw_corner.lat, sw_corner.lon, altitude_m)
    ne = GeoPoint(ne_corner.lat, ne_corner.lon, altitude_m)
    height_m = sw.haversine_m(GeoPoint(ne.lat, sw.lon))
    n_lines = max(2, int(height_m / line_spacing_m) + 1)

    for i in range(n_lines):
        north_offset = (height_m / max(n_lines - 1, 1)) * i
        line_west = sw.offset_m(north_offset, 0)  # N=0°
        line_east = GeoPoint(line_west.lat, ne.lon, altitude_m)
        if i % 2 == 0:
            start, end = line_west, line_east
            yaw = 90.0
        else:
            start, end = line_east, line_west
            yaw = 270.0

        mission.append(
            MissionStep(
                target=start,
                speed_mps=speed_mps,
                yaw_deg=yaw,
                gimbal_pitch_deg=gimbal_pitch_deg,
                actions=["start_record"] if i == 0 else [],
            )
        )
        mission.append(
            MissionStep(
                target=end,
                speed_mps=speed_mps,
                yaw_deg=yaw,
                gimbal_pitch_deg=gimbal_pitch_deg,
                actions=["stop_record"] if i == n_lines - 1 else [],
            )
        )
    return mission
