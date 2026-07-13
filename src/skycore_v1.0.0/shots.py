"""Mission template library.

Ready-made mission generators for common shots and inspections. Each
function returns a `WaypointMission` you can execute against any backend
or export to a Litchi CSV via `skycore.missions.litchi.export_litchi_csv`.
"""
from __future__ import annotations

import math
from typing import Optional

from skycore.core.types import GeoPoint, MissionStep
from skycore.missions.waypoint import WaypointMission


def panorama_mission(
    center: GeoPoint,
    altitude_m: float = 30.0,
    yaw_steps: int = 12,
    photos_per_yaw: int = 3,
    gimbal_pitches: tuple[float, float, float] = (-15.0, -45.0, -75.0),
    name: Optional[str] = None,
) -> WaypointMission:
    """Stationary multi-row panorama: rotate yaw, sweep gimbal at each yaw.

    Produces yaw_steps × photos_per_yaw photos for a full sphere or hemisphere.
    """
    if photos_per_yaw != len(gimbal_pitches):
        raise ValueError("photos_per_yaw must equal len(gimbal_pitches)")
    m = WaypointMission(name=name or "panorama")
    target = GeoPoint(center.lat, center.lon, altitude_m)
    for i in range(yaw_steps):
        yaw = (360.0 / yaw_steps) * i
        for pitch in gimbal_pitches:
            m.append(
                MissionStep(
                    target=target,
                    speed_mps=1.0,
                    yaw_deg=yaw,
                    gimbal_pitch_deg=pitch,
                    actions=["take_photo"],
                    hold_seconds=0.5,
                )
            )
    return m


def perimeter_patrol(
    polygon: list[GeoPoint],
    altitude_m: float = 40.0,
    speed_mps: float = 5.0,
    gimbal_pitch_deg: float = -30.0,
    photo_at_corners: bool = True,
    name: Optional[str] = None,
) -> WaypointMission:
    """Traverse a closed polygon at constant altitude.

    Heading at each corner aims at the next corner; gimbal stays at the given
    pitch. Useful for property surveillance, perimeter inspection.
    """
    if len(polygon) < 3:
        raise ValueError("perimeter polygon needs >= 3 corners")
    m = WaypointMission(name=name or "perimeter")
    n = len(polygon)
    for i, corner in enumerate(polygon + [polygon[0]]):
        nxt = polygon[(i + 1) % n] if i < n else polygon[1 % n]
        yaw = corner.bearing_to(nxt)
        m.append(
            MissionStep(
                target=GeoPoint(corner.lat, corner.lon, altitude_m),
                speed_mps=speed_mps,
                yaw_deg=yaw,
                gimbal_pitch_deg=gimbal_pitch_deg,
                actions=["take_photo"] if photo_at_corners else [],
            )
        )
    return m


def building_inspection(
    center: GeoPoint,
    radius_m: float = 25.0,
    altitudes_m: tuple[float, ...] = (10.0, 20.0, 30.0, 40.0),
    waypoints_per_ring: int = 12,
    speed_mps: float = 3.0,
    name: Optional[str] = None,
) -> WaypointMission:
    """Stacked orbits at multiple altitudes around a structure.

    Camera always faces the structure (focus POI semantics).
    """
    m = WaypointMission(name=name or "building-inspection")
    for alt in altitudes_m:
        for i in range(waypoints_per_ring):
            bearing = (360.0 / waypoints_per_ring) * i
            wp = center.offset_m(radius_m, bearing, alt_delta=alt - center.alt)
            yaw = wp.bearing_to(center)
            m.append(
                MissionStep(
                    target=wp,
                    speed_mps=speed_mps,
                    yaw_deg=yaw,
                    gimbal_pitch_deg=-15.0,
                    actions=["take_photo"],
                )
            )
    return m


def hyperlapse_line(
    start: GeoPoint,
    end: GeoPoint,
    altitude_m: float = 30.0,
    photos: int = 100,
    speed_mps: float = 2.0,
    gimbal_pitch_deg: float = -10.0,
    name: Optional[str] = None,
) -> WaypointMission:
    """Straight-line hyperlapse: N evenly-spaced photo waypoints."""
    if photos < 2:
        raise ValueError("need >= 2 photos")
    m = WaypointMission(name=name or "hyperlapse")
    yaw = start.bearing_to(end)
    distance = start.haversine_m(end)
    for i in range(photos):
        t = i / (photos - 1)
        # interpolate by lat/lon directly (accurate for short distances)
        wp = GeoPoint(
            start.lat + (end.lat - start.lat) * t,
            start.lon + (end.lon - start.lon) * t,
            altitude_m,
        )
        m.append(
            MissionStep(
                target=wp,
                speed_mps=speed_mps,
                yaw_deg=yaw,
                gimbal_pitch_deg=gimbal_pitch_deg,
                actions=["take_photo"],
                hold_seconds=0.3,
            )
        )
    return m


def vertical_panorama(
    location: GeoPoint,
    altitude_m: float = 30.0,
    pitches_deg: tuple[float, ...] = (-90.0, -60.0, -30.0, 0.0, 15.0),
    name: Optional[str] = None,
) -> WaypointMission:
    """Single-point gimbal sweep producing a vertical panorama."""
    m = WaypointMission(name=name or "vertical-pano")
    target = GeoPoint(location.lat, location.lon, altitude_m)
    for pitch in pitches_deg:
        m.append(
            MissionStep(
                target=target,
                speed_mps=1.0,
                yaw_deg=0.0,
                gimbal_pitch_deg=pitch,
                actions=["take_photo"],
                hold_seconds=0.5,
            )
        )
    return m


def spiraling_orbit(
    center: GeoPoint,
    start_altitude_m: float = 5.0,
    end_altitude_m: float = 50.0,
    radius_m: float = 30.0,
    revolutions: int = 3,
    waypoints_per_rev: int = 8,
    speed_mps: float = 3.0,
    name: Optional[str] = None,
) -> WaypointMission:
    """Climbing helix around a point. Cinematic reveal of tall structures."""
    m = WaypointMission(name=name or "spiraling-orbit")
    total = revolutions * waypoints_per_rev
    for i in range(total):
        bearing = (360.0 * revolutions / total) * i
        alt = start_altitude_m + (end_altitude_m - start_altitude_m) * i / max(total - 1, 1)
        wp = center.offset_m(radius_m, bearing, alt_delta=alt - center.alt)
        yaw = wp.bearing_to(center)
        m.append(
            MissionStep(
                target=wp,
                speed_mps=speed_mps,
                yaw_deg=yaw,
                gimbal_pitch_deg=-15.0,
                actions=["take_photo"] if i % 2 == 0 else [],
            )
        )
    return m


def facade_scan(
    start: GeoPoint,
    end: GeoPoint,
    altitudes_m: tuple[float, ...] = (5.0, 15.0, 25.0, 35.0),
    speed_mps: float = 2.5,
    standoff_m: float = 15.0,
    name: Optional[str] = None,
) -> WaypointMission:
    """Lawnmower along a building facade at multiple altitudes.

    The drone flies parallel to the line `start -> end` at a `standoff_m`
    distance, sweeping each altitude. Camera faces the facade.
    """
    m = WaypointMission(name=name or "facade-scan")
    facade_bearing = start.bearing_to(end)
    perpendicular = (facade_bearing + 90.0) % 360
    facade_yaw = (facade_bearing - 90.0) % 360  # camera looks at facade

    line_start = start.offset_m(standoff_m, perpendicular)
    line_end = end.offset_m(standoff_m, perpendicular)

    for idx, alt in enumerate(altitudes_m):
        a = GeoPoint(line_start.lat, line_start.lon, alt)
        b = GeoPoint(line_end.lat, line_end.lon, alt)
        if idx % 2 == 0:
            m.append(MissionStep(a, speed_mps=speed_mps, yaw_deg=facade_yaw, gimbal_pitch_deg=0))
            m.append(MissionStep(b, speed_mps=speed_mps, yaw_deg=facade_yaw, gimbal_pitch_deg=0, actions=["start_record"] if idx == 0 else []))
        else:
            m.append(MissionStep(b, speed_mps=speed_mps, yaw_deg=facade_yaw, gimbal_pitch_deg=0))
            m.append(MissionStep(a, speed_mps=speed_mps, yaw_deg=facade_yaw, gimbal_pitch_deg=0))
    if m.steps:
        m.steps[-1].actions = list(m.steps[-1].actions) + ["stop_record"]
    return m


def cinematic_reveal(
    foreground: GeoPoint,
    background: GeoPoint,
    foreground_alt_m: float = 3.0,
    background_alt_m: float = 60.0,
    duration_s: float = 12.0,
    name: Optional[str] = None,
) -> WaypointMission:
    """Two-waypoint reveal: low foreground → high background, gimbal tilts up.

    The classic dolly-up reveal shot. Fly slowly to capture parallax.
    """
    distance = foreground.haversine_m(background)
    speed = max(0.5, distance / duration_s)
    yaw = foreground.bearing_to(background)
    m = WaypointMission(name=name or "cinematic-reveal")
    m.append(
        MissionStep(
            target=GeoPoint(foreground.lat, foreground.lon, foreground_alt_m),
            speed_mps=speed,
            yaw_deg=yaw,
            gimbal_pitch_deg=-30.0,
            actions=["start_record"],
        )
    )
    m.append(
        MissionStep(
            target=GeoPoint(background.lat, background.lon, background_alt_m),
            speed_mps=speed,
            yaw_deg=yaw,
            gimbal_pitch_deg=0.0,
            actions=["stop_record"],
        )
    )
    return m
