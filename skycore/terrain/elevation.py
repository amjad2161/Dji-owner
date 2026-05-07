"""Terrain elevation lookup via Open-Elevation (free public API).

https://open-elevation.com returns elevation in meters AMSL. Use this to:
- Verify a planned waypoint is above-terrain by N meters
- Validate AGL altitude assumptions in mission generators
- Detect potential ground collisions on a planned trajectory
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Iterable

log = logging.getLogger(__name__)

OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"


def get_elevation(lat: float, lon: float, timeout_s: float = 15.0) -> float:
    return get_elevations([(lat, lon)], timeout_s=timeout_s)[0]


def get_elevations(points: Iterable[tuple[float, float]], timeout_s: float = 15.0) -> list[float]:
    """Batch elevation query. Returns elevations in meters AMSL, in input order."""
    locs = "|".join(f"{lat},{lon}" for lat, lon in points)
    url = f"{OPEN_ELEVATION_URL}?locations={urllib.parse.quote(locs)}"
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [float(r["elevation"]) for r in data["results"]]


def terrain_clearance(
    path_points: list[tuple[float, float, float]],
    min_clearance_m: float = 30.0,
) -> tuple[bool, list[str]]:
    """Verify a path stays at least min_clearance_m above terrain.

    path_points: [(lat, lon, alt_amsl_m), ...]
    """
    pts = [(p[0], p[1]) for p in path_points]
    elevs = get_elevations(pts)
    issues: list[str] = []
    for i, ((lat, lon, alt), elev) in enumerate(zip(path_points, elevs)):
        clearance = alt - elev
        if clearance < min_clearance_m:
            issues.append(
                f"Waypoint {i} ({lat:.4f}, {lon:.4f}): {clearance:.1f} m clearance < {min_clearance_m} m"
            )
    return (not issues), issues
