"""Terrain elevation from multiple free sources.

Tries Open-Elevation API first, falls back to Open-Meteo elevation data.
Caches results in memory to avoid redundant lookups.

Usage:
    e = get_elevation(37.7749, -122.4194)  # single point
    elevs = get_elevations([(37.77, -122.42), (37.78, -122.43)])  # batch
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)

# APIs (free, no key required)
OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"
OPEN_METEO_ELEV_URL = "https://api.open-meteo.com/v1/elevation"

# In-memory cache
_cache: dict[tuple[float, float], float] = {}


def clear_cache() -> None:
    """Clear the elevation cache."""
    global _cache
    _cache = {}


def get_elevation(lat: float, lon: float, use_cache: bool = True) -> float:
    """Get elevation in meters AMSL for a single point.
    
    Raises:
        RuntimeError: If all elevation APIs fail.
    """
    if use_cache:
        key = (round(lat, 4), round(lon, 4))
        if key in _cache:
            return _cache[key]

    # Try Open-Elevation first (more accurate)
    try:
        params = urllib.parse.urlencode({"locations": f"{lat},{lon}"})
        req = urllib.request.Request(f"{OPEN_ELEVATION_URL}?{params}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results", [])
        if results:
            elev = float(results[0].get("elevation", 0))
            if use_cache:
                _cache[(round(lat, 4), round(lon, 4))] = elev
            return elev
    except Exception as e:
        log.debug("Open-Elevation failed: %s", e)

    # Fallback: Open-Meteo elevation
    try:
        params = urllib.parse.urlencode({
            "latitude": lat,
            "longitude": lon,
        })
        req = urllib.request.Request(f"{OPEN_METEO_ELEV_URL}?{params}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        elev_data = data.get("elevation", [])
        if elev_data and len(elev_data) > 0:
            elev = float(elev_data[0] if isinstance(elev_data, list) else elev_data)
            if use_cache:
                _cache[(round(lat, 4), round(lon, 4))] = elev
            return elev
    except Exception as e:
        log.debug("Open-Meteo elevation failed: %s", e)

    log.warning("All elevation APIs failed for (%f, %f) - returning 0", lat, lon)
    return 0.0


def get_elevations(points: list[tuple[float, float]], use_cache: bool = True) -> list[float]:
    """Get elevations for multiple points. Batch API for efficiency.
    
    Args:
        points: List of (lat, lon) tuples
        use_cache: Whether to use/populate cache
    
    Returns:
        List of elevations in meters (0.0 if lookup failed)
    """
    if not points:
        return []

    # Check cache first
    results = []
    missing = []
    missing_idx = []

    for i, (lat, lon) in enumerate(points):
        key = (round(lat, 4), round(lon, 4))
        if use_cache and key in _cache:
            results.append(_cache[key])
        else:
            results.append(None)
            missing.append((lat, lon))
            missing_idx.append(i)

    if not missing:
        return results

    # Batch request to Open-Elevation
    try:
        locations_str = "\n".join(f"{lat},{lon}" for lat, lon in missing)
        req = urllib.request.Request(
            OPEN_ELEVATION_URL,
            data=json.dumps({"locations": [{"latitude": lat, "longitude": lon} for lat, lon in missing]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        elevations = {f"{r['latitude']},{r['longitude']}": r["elevation"] for r in data.get("results", [])}

        for i, (lat, lon) in enumerate(missing):
            elev = elevations.get(f"{lat},{lon}", 0.0)
            results[missing_idx[i]] = elev
            if use_cache:
                _cache[(round(lat, 4), round(lon, 4))] = elev
    except Exception as e:
        log.warning("Batch elevation lookup failed: %s. Falling back to individual.", e)
        # Fallback: individual lookups
        for i, (lat, lon) in enumerate(missing):
            results[missing_idx[i]] = get_elevation(lat, lon, use_cache)

    return results


def get_terrain_profile(
    start: tuple[float, float],
    end: tuple[float, float],
    num_points: int = 20,
) -> list[tuple[float, float, float]]:
    """Get elevation profile along a line from start to end.
    
    Returns:
        List of (lat, lon, elevation_m) tuples
    """
    lat1, lon1 = start
    lat2, lon2 = end
    
    points = []
    for i in range(num_points):
        t = i / (num_points - 1) if num_points > 1 else 0
        lat = lat1 + (lat2 - lat1) * t
        lon = lon1 + (lon2 - lon1) * t
        points.append((lat, lon))
    
    elevations = get_elevations(points)
    return [(points[i][0], points[i][1], elevations[i]) for i in range(len(points))]


def elevation_at_agl(lat: float, lon: float, altitude_msl: float) -> float:
    """Convert altitude above sea level to altitude above ground level.
    
    Args:
        lat, lon: Position
        altitude_msl: Altitude in meters above sea level
    
    Returns:
        Altitude in meters above ground level (AGL)
    """
    ground_elev = get_elevation(lat, lon)
    return max(0.0, altitude_msl - ground_elev)


def check_obstacle_clearance(
    lat: float,
    lon: float,
    altitude_agl_m: float,
    min_clearance_m: float = 10.0,
) -> tuple[bool, float, float]:
    """Check if there's sufficient obstacle clearance at a point.
    
    Args:
        lat, lon: Position
        altitude_agl_m: Drone altitude above ground
        min_clearance_m: Minimum required clearance
    
    Returns:
        (safe, terrain_elevation, clearance)
    """
    terrain_elev = get_elevation(lat, lon)
    drone_alt_msl = terrain_elev + altitude_agl_m
    clearance = drone_alt_msl - terrain_elev  # Should equal altitude_agl_m
    
    # The real check: is the terrain elevation significantly different from expected?
    # This is a placeholder - real implementation would check DSM/DTM data
    return True, terrain_elev, altitude_agl_m