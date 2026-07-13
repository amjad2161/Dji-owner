"""Mission template generators for common use cases.

Provides preset mission generators for: orbit, panorama, perimeter patrol,
building inspection, hyperlapse, vertical climb, facade scan, cinematic reveal,
and spiraling search pattern.

Usage:
    from skycore.templates import orbit_mission, panorama_mission
    
    m = orbit_mission(center, radius_m=50, altitude_m=30, waypoints=12)
    m = panorama_mission(center, altitude_m=30, yaw_steps=8)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from skycore.core.types import GeoPoint, MissionStep
from skycore.missions.waypoint import WaypointMission


def _step(
    lat: float,
    lon: float,
    alt: float,
    speed_mps: float = 5.0,
    yaw_deg: float | None = None,
    gimbal_deg: float | None = None,
    actions: list[str] | None = None,
    hold_s: float = 0.0,
) -> MissionStep:
    return MissionStep(
        target=GeoPoint(lat, lon, alt),
        speed_mps=speed_mps,
        yaw_deg=yaw_deg,
        gimbal_pitch_deg=gimbal_deg,
        actions=actions or [],
        hold_seconds=hold_s,
    )


# ---------------------------------------------------------------------------
# Orbit
# ---------------------------------------------------------------------------

def orbit_mission(
    center: GeoPoint,
    radius_m: float = 50,
    altitude_m: float = 30,
    waypoints: int = 12,
    speed_mps: float = 5.0,
    gimbal_pitch_deg: float = -45,
) -> WaypointMission:
    """Circular orbit around a point of interest.
    
    Args:
        center: Center point of orbit
        radius_m: Orbit radius in meters
        altitude_m: Flight altitude
        waypoints: Number of waypoints in the orbit
        speed_mps: Flight speed
        gimbal_pitch_deg: Gimbal angle to point at center
    
    Returns:
        WaypointMission configured for orbit
    """
    m = WaypointMission(name=f"orbit_r{radius_m}_h{altitude_m}")
    
    for i in range(waypoints):
        angle = 2 * math.pi * i / waypoints
        # Calculate point on circle
        d_rad = radius_m / 111000  # approx meters to degrees
        lat = center.lat + d_rad * math.cos(angle)
        lon = center.lon + d_rad * math.sin(angle) / math.cos(math.radians(center.lat))
        
        # Face the center (yaw toward center)
        yaw = (math.degrees(angle) + 180) % 360
        
        m.steps.append(_step(lat, lon, altitude_m, speed_mps, yaw, gimbal_pitch_deg))
    
    return m


# ---------------------------------------------------------------------------
# Panorama
# ---------------------------------------------------------------------------

def panorama_mission(
    center: GeoPoint,
    altitude_m: float = 30,
    yaw_steps: int = 12,
    speed_mps: float = 3.0,
    gimbal_pitch_deg: float = -60,
    hold_s: float = 3.0,
) -> WaypointMission:
    """Photo panorama at a fixed position with yaw sweeps.
    
    Takes photos at each heading, then moves to next position.
    """
    m = WaypointMission(name=f"panorama_{yaw_steps}shots")
    
    for i in range(yaw_steps):
        yaw = 360 * i / yaw_steps
        m.steps.append(_step(
            center.lat, center.lon, altitude_m,
            speed_mps, yaw, gimbal_pitch_deg,
            actions=["take_photo"], hold_s=hold_s,
        ))
    
    return m


# ---------------------------------------------------------------------------
# Perimeter Patrol
# ---------------------------------------------------------------------------

def perimeter_patrol(
    corners: list[GeoPoint],
    altitude_m: float = 40,
    speed_mps: float = 8.0,
    gimbal_pitch_deg: float = -45,
    actions: list[str] | None = None,
) -> WaypointMission:
    """Patrol the perimeter of a polygon area.
    
    Args:
        corners: List of GeoPoints defining the polygon (at least 3)
        altitude_m: Flight altitude
        speed_mps: Patrol speed
        gimbal_pitch_deg: Gimbal angle to scan the area
        actions: Actions to perform at each waypoint
    
    Returns:
        WaypointMission for perimeter patrol
    """
    if len(corners) < 3:
        raise ValueError("Perimeter patrol requires at least 3 corners")
    
    m = WaypointMission(name="perimeter_patrol")
    
    for i, corner in enumerate(corners):
        # Face the next corner (look ahead)
        next_corner = corners[(i + 1) % len(corners)]
        yaw = corner.bearing_to(next_corner)
        
        m.steps.append(_step(
            corner.lat, corner.lon, altitude_m,
            speed_mps, yaw, gimbal_pitch_deg,
            actions=actions or [],
        ))
    
    return m


# ---------------------------------------------------------------------------
# Building Inspection
# ---------------------------------------------------------------------------

def building_inspection(
    center: GeoPoint,
    radius_m: float = 25,
    altitude_m: float = 20,
    orbits: int = 3,
    waypoints_per_orbit: int = 8,
    speed_mps: float = 3.0,
) -> WaypointMission:
    """Inspect a building from multiple angles.
    
    Spiral pattern with decreasing radius and increasing altitude.
    """
    m = WaypointMission(name="building_inspection")
    
    for orbit in range(orbits):
        r = radius_m * (1 - orbit * 0.25)  # Shrink radius
        alt = altitude_m + orbit * 10  # Increase altitude
        gimbal = -30 - orbit * 15  # Look more downward
        
        for i in range(waypoints_per_orbit):
            angle = 2 * math.pi * i / waypoints_per_orbit
            d_rad = r / 111000
            lat = center.lat + d_rad * math.cos(angle)
            lon = center.lon + d_rad * math.sin(angle) / math.cos(math.radians(center.lat))
            
            yaw = (math.degrees(angle) + 180) % 360
            
            m.steps.append(_step(
                lat, lon, alt,
                speed_mps, yaw, gimbal,
                actions=["take_photo"],
            ))
    
    return m


# ---------------------------------------------------------------------------
# Hyperlapse
# ---------------------------------------------------------------------------

def hyperlapse_line(
    start: GeoPoint,
    end: GeoPoint,
    altitude_m: float = 30,
    num_points: int = 20,
    speed_mps: float = 5.0,
    gimbal_pitch_deg: float = -60,
) -> WaypointMission:
    """Linear path for timelapse/hyperlapse photography.
    
    Args:
        start: Starting point
        end: Ending point
        altitude_m: Flight altitude
        num_points: Number of waypoints
        speed_mps: Flight speed
        gimbal_pitch_deg: Camera angle
    
    Returns:
        WaypointMission configured for linear hyperlapse
    """
    m = WaypointMission(name="hyperlapse")
    
    for i in range(num_points):
        t = i / (num_points - 1)
        lat = start.lat + (end.lat - start.lat) * t
        lon = start.lon + (end.lon - start.lon) * t
        
        # Face the direction of travel
        current = GeoPoint(lat, lon, altitude_m)
        next_pt = GeoPoint(
            start.lat + (end.lat - start.lat) * min(1, t + 0.05),
            start.lon + (end.lon - start.lon) * min(1, t + 0.05),
            altitude_m,
        )
        yaw = current.bearing_to(next_pt) if i < num_points - 1 else None
        
        m.steps.append(_step(
            lat, lon, altitude_m,
            speed_mps, yaw, gimbal_pitch_deg,
            actions=["take_photo"],
        ))
    
    return m


# ---------------------------------------------------------------------------
# Vertical Panorama
# ---------------------------------------------------------------------------

def vertical_panorama(
    center: GeoPoint,
    start_alt_m: float = 5,
    end_alt_m: float = 50,
    num_stops: int = 5,
    gimbal_pitch_deg: float = -90,
    hold_s: float = 2.0,
) -> WaypointMission:
    """Vertical scan from low to high altitude.
    
    Good for building facades, cliffs, or tower inspection.
    """
    m = WaypointMission(name="vertical_panorama")
    
    for i in range(num_stops):
        alt = start_alt_m + (end_alt_m - start_alt_m) * i / (num_stops - 1)
        m.steps.append(_step(
            center.lat, center.lon, alt,
            speed_mps=2.0, yaw_deg=None, gimbal_pitch_deg=gimbal_pitch_deg,
            actions=["take_photo"], hold_s=hold_s,
        ))
    
    return m


# ---------------------------------------------------------------------------
# Facade Scan
# ---------------------------------------------------------------------------

def facade_scan(
    corner_a: GeoPoint,
    corner_b: GeoPoint,
    altitude_m: float = 20,
    sweeps: int = 3,
    speed_mps: float = 3.0,
    gimbal_pitch_deg: float = -45,
) -> WaypointMission:
    """Scan a building facade in parallel passes.
    
    Similar to lawnmower but optimized for vertical surfaces.
    """
    m = WaypointMission(name="facade_scan")
    
    # Calculate bounding box
    min_lat = min(corner_a.lat, corner_b.lat)
    max_lat = max(corner_a.lat, corner_b.lat)
    min_lon = min(corner_a.lon, corner_b.lon)
    max_lon = max(corner_a.lon, corner_b.lon)
    
    lat_step = (max_lat - min_lat) / (sweeps - 1) if sweeps > 1 else 0
    
    for i in range(sweeps):
        lat = min_lat + lat_step * i
        
        if i % 2 == 0:
            # Left to right
            m.steps.append(_step(min_lon if min_lon > max_lon else max_lon, lat, altitude_m, speed_mps, 0, gimbal_pitch_deg, ["take_photo"]))
            m.steps.append(_step(min_lon if min_lon < max_lon else max_lon, lat, altitude_m, speed_mps, 180, gimbal_pitch_deg, ["take_photo"]))
        else:
            # Right to left
            m.steps.append(_step(min_lon if min_lon < max_lon else max_lon, lat, altitude_m, speed_mps, 180, gimbal_pitch_deg, ["take_photo"]))
            m.steps.append(_step(min_lon if min_lon > max_lon else max_lon, lat, altitude_m, speed_mps, 0, gimbal_pitch_deg, ["take_photo"]))
    
    return m


# ---------------------------------------------------------------------------
# Cinematic Reveal
# ---------------------------------------------------------------------------

def cinematic_reveal(
    fg_point: GeoPoint,
    bg_point: GeoPoint,
    altitude_m: float = 30,
    steps: int = 10,
    speed_mps: float = 2.0,
    gimbal_pitch_deg: float = -30,
) -> WaypointMission:
    """Cinematic reveal shot - start close on foreground, pull back to background.
    
    Classic video technique for dramatic transitions.
    """
    m = WaypointMission(name="cinematic_reveal")
    
    for i in range(steps):
        t = i / (steps - 1)
        lat = fg_point.lat + (bg_point.lat - fg_point.lat) * t
        lon = fg_point.lon + (bg_point.lon - fg_point.lon) * t
        
        # Calculate the optimal gimbal angle for each position
        # Start looking close (steep), end looking far (shallow)
        gimbal = -20 - (60 - 20) * t
        
        m.steps.append(_step(
            lat, lon, altitude_m,
            speed_mps, yaw_deg=None, gimbal_pitch_deg=gimbal,
            actions=["take_photo"],
        ))
    
    return m


# ---------------------------------------------------------------------------
# Spiraling Search
# ---------------------------------------------------------------------------

def spiraling_orbit(
    center: GeoPoint,
    min_radius_m: float = 20,
    max_radius_m: float = 100,
    altitude_m: float = 40,
    waypoints_per_ring: int = 8,
    rings: int = 4,
    speed_mps: float = 5.0,
    gimbal_pitch_deg: float = -45,
) -> WaypointMission:
    """Spiraling outward search pattern.
    
    Good for area survey or SAR (Search and Rescue).
    """
    m = WaypointMission(name="spiraling_search")
    
    for ring in range(rings):
        t = ring / (rings - 1) if rings > 1 else 0
        r = min_radius_m + (max_radius_m - min_radius_m) * t
        alt = altitude_m + ring * 5  # Slightly higher each ring
        
        for i in range(waypoints_per_ring):
            angle = 2 * math.pi * i / waypoints_per_ring + ring * 0.5  # Offset each ring
            d_rad = r / 111000
            lat = center.lat + d_rad * math.cos(angle)
            lon = center.lon + d_rad * math.sin(angle) / math.cos(math.radians(center.lat))
            
            yaw = (math.degrees(angle) + 180) % 360
            
            m.steps.append(_step(
                lat, lon, alt,
                speed_mps, yaw, gimbal_pitch_deg,
                actions=["take_photo"] if ring == 0 and i == 0 else [],
            ))
    
    return m


# ---------------------------------------------------------------------------
# All templates registry
# ---------------------------------------------------------------------------

TEMPLATES = {
    "orbit": orbit_mission,
    "panorama": panorama_mission,
    "perimeter": perimeter_patrol,
    "building": building_inspection,
    "hyperlapse": hyperlapse_line,
    "vertical_pano": vertical_panorama,
    "facade": facade_scan,
    "reveal": cinematic_reveal,
    "spiral": spiraling_orbit,
}


def get_template(kind: str):
    """Get a template generator by name."""
    if kind not in TEMPLATES:
        raise ValueError(f"Unknown template: {kind}. Available: {list(TEMPLATES.keys())}")
    return TEMPLATES[kind]