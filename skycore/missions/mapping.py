"""Lawnmower / boustrophedon survey missions for mapping.

Generates the standard zig-zag pattern used for photogrammetry. The
output is compatible with OpenDroneMap or Pix4D — fly the mission, then
upload the photos to your processor of choice.
"""
from __future__ import annotations

import math
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
    photo_spacing_m = sensor_width_m_at_altitude * (1 - front_overlap)
    if photo_spacing_m <= 0:
        raise ValueError("front_overlap too high")

    mission = WaypointMission(name=name or "survey")

    # Fly east-west lines, stepping north each time.
    sw = GeoPoint(sw_corner.lat, sw_corner.lon, altitude_m)
    ne = GeoPoint(ne_corner.lat, ne_corner.lon, altitude_m)
    height_m = sw.haversine_m(GeoPoint(ne.lat, sw.lon))          # south-north extent
    width_m = sw.haversine_m(GeoPoint(sw.lat, ne.lon))           # west-east extent
    # ceil (not floor): floor+1 undershoots the requested side overlap on the last strip.
    n_lines = max(2, math.ceil(height_m / line_spacing_m) + 1)
    photos_per_line = max(2, math.ceil(width_m / photo_spacing_m) + 1)

    for i in range(n_lines):
        north_offset = (height_m / max(n_lines - 1, 1)) * i
        line_west = sw.offset_m(north_offset, 0)  # N=0°
        line_east = GeoPoint(line_west.lat, ne.lon, altitude_m)
        if i % 2 == 0:
            a, b, yaw = line_west, line_east, 90.0
        else:
            a, b, yaw = line_east, line_west, 270.0

        # Emit evenly-spaced take_photo waypoints along each line (honoring front_overlap)
        # so the survey yields the overlapping stills photogrammetry needs — the previous
        # version only toggled video record and generated no photos at all.
        for k in range(photos_per_line):
            t = k / (photos_per_line - 1)
            pt = GeoPoint(a.lat + (b.lat - a.lat) * t, a.lon + (b.lon - a.lon) * t, altitude_m)
            actions = ["take_photo"]
            if i == 0 and k == 0:
                actions = ["start_record", "take_photo"]
            elif i == n_lines - 1 and k == photos_per_line - 1:
                actions = ["take_photo", "stop_record"]
            mission.append(
                MissionStep(
                    target=pt,
                    speed_mps=speed_mps,
                    yaw_deg=yaw,
                    gimbal_pitch_deg=gimbal_pitch_deg,
                    actions=actions,
                )
            )
    return mission
