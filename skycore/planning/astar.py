"""A* path planner that routes around obstacle polygons.

Discretizes the operating area into a grid and runs A* to find a path
from start to end that doesn't cross any forbidden polygon. Coarse and
simple, but enough for routing around restricted airspace blocks or
property lines for survey missions.
"""
from __future__ import annotations

import heapq
import logging
import math
from typing import Iterable

from skycore.core.types import GeoPoint

log = logging.getLogger(__name__)


def plan_around_obstacles(
    start: GeoPoint,
    end: GeoPoint,
    obstacles: Iterable[list[tuple[float, float]]],  # polygons; each = list[(lat, lon)]
    grid_resolution_m: float = 20.0,
    altitude_m: float = 30.0,
    margin_m: float = 5.0,
    max_iters: int = 50_000,
) -> list[GeoPoint]:
    """Return a list of GeoPoints from start to end avoiding the obstacles."""
    try:
        from shapely.geometry import Point, Polygon
    except ImportError as e:
        raise ImportError("shapely is required. pip install shapely") from e

    polys = [Polygon(p).buffer(0) for p in obstacles]
    margin_deg = margin_m / 111_000.0
    buffered = [p.buffer(margin_deg) for p in polys]

    def is_blocked(lat: float, lon: float) -> bool:
        pt = Point(lat, lon)
        return any(p.contains(pt) for p in buffered)

    pad = max(grid_resolution_m * 2 / 111_000.0, 0.001)
    min_lat = min(start.lat, end.lat) - pad
    max_lat = max(start.lat, end.lat) + pad
    min_lon = min(start.lon, end.lon) - pad
    max_lon = max(start.lon, end.lon) + pad

    step_lat = grid_resolution_m / 111_000.0
    step_lon = grid_resolution_m / (111_000.0 * max(0.05, math.cos(math.radians(start.lat))))

    def to_grid(lat: float, lon: float) -> tuple[int, int]:
        return (round((lat - min_lat) / step_lat), round((lon - min_lon) / step_lon))

    def from_grid(gi: int, gj: int) -> tuple[float, float]:
        return (min_lat + gi * step_lat, min_lon + gj * step_lon)

    start_g = to_grid(start.lat, start.lon)
    end_g = to_grid(end.lat, end.lon)

    def h(g: tuple[int, int]) -> float:
        return math.hypot(g[0] - end_g[0], g[1] - end_g[1])

    open_set: list[tuple[float, float, tuple[int, int]]] = []
    heapq.heappush(open_set, (h(start_g), 0.0, start_g))
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start_g: None}
    g_score: dict[tuple[int, int], float] = {start_g: 0.0}

    for _ in range(max_iters):
        if not open_set:
            break
        _, g_cur, cur = heapq.heappop(open_set)
        if cur == end_g or h(cur) < 1.5:
            path = []
            node: tuple[int, int] | None = cur
            while node is not None:
                lat, lon = from_grid(*node)
                path.append(GeoPoint(lat, lon, altitude_m))
                node = came_from[node]
            return list(reversed(path))

        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                nb = (cur[0] + di, cur[1] + dj)
                lat, lon = from_grid(*nb)
                if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
                    continue
                if is_blocked(lat, lon):
                    continue
                tentative = g_cur + math.hypot(di, dj)
                if tentative < g_score.get(nb, math.inf):
                    g_score[nb] = tentative
                    came_from[nb] = cur
                    heapq.heappush(open_set, (tentative + h(nb), tentative, nb))

    raise RuntimeError(f"No path from {start} to {end} (explored {len(g_score)} cells)")
