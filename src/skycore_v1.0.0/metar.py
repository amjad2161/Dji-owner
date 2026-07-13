"""METAR fetcher using the FAA aviationweather.gov free API.

METAR is the standard format for current weather observed at airports.
For drone pilots, the closest airport's METAR is the most reliable
ground-truth wind / visibility / ceiling information.

No API key required. https://aviationweather.gov/data/api/
"""
from __future__ import annotations

import json
import logging
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

METAR_URL = "https://aviationweather.gov/api/data/metar"

# A small built-in registry of major airports for nearest-airport lookups.
# For production use, plug in a full airport DB.
_AIRPORT_HINTS: list[tuple[str, float, float]] = [
    ("KSFO", 37.6213, -122.3790),
    ("KLAX", 33.9416, -118.4085),
    ("KJFK", 40.6413, -73.7781),
    ("KORD", 41.9742, -87.9073),
    ("KSEA", 47.4502, -122.3088),
    ("EGLL", 51.4700, -0.4543),
    ("LFPG", 49.0097, 2.5479),
    ("EDDF", 50.0379, 8.5622),
    ("LLBG", 32.0009, 34.8867),
    ("OMDB", 25.2532, 55.3657),
    ("RJTT", 35.5494, 139.7798),
    ("YSSY", -33.9461, 151.1772),
]


@dataclass
class Metar:
    station: str
    raw_text: str
    observation_time: Optional[str]
    temperature_c: Optional[float]
    dewpoint_c: Optional[float]
    wind_direction_deg: Optional[int]
    wind_speed_kt: Optional[float]
    wind_gust_kt: Optional[float]
    visibility_sm: Optional[float]
    altimeter_hpa: Optional[float]
    cloud_layers: list[dict]
    flight_category: Optional[str]

    @property
    def wind_speed_kph(self) -> Optional[float]:
        return None if self.wind_speed_kt is None else self.wind_speed_kt * 1.852

    @property
    def wind_gust_kph(self) -> Optional[float]:
        return None if self.wind_gust_kt is None else self.wind_gust_kt * 1.852


def fetch_metar(station_icao: str, timeout_s: float = 10.0) -> Optional[Metar]:
    """Fetch the most recent METAR for an ICAO station identifier."""
    params = {"ids": station_icao, "format": "json"}
    url = f"{METAR_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data:
        return None
    m = data[0] if isinstance(data, list) else data
    return Metar(
        station=m.get("icaoId", station_icao),
        raw_text=m.get("rawOb", ""),
        observation_time=m.get("reportTime"),
        temperature_c=_to_float(m.get("temp")),
        dewpoint_c=_to_float(m.get("dewp")),
        wind_direction_deg=_to_int(m.get("wdir")),
        wind_speed_kt=_to_float(m.get("wspd")),
        wind_gust_kt=_to_float(m.get("wgst")),
        visibility_sm=_to_float(m.get("visib")),
        altimeter_hpa=_to_float(m.get("altim")),
        cloud_layers=m.get("clouds") or [],
        flight_category=m.get("fltCat"),
    )


def fetch_nearest_metar(lat: float, lon: float, max_distance_km: float = 100.0) -> Optional[Metar]:
    """Find the nearest airport from the small built-in registry, fetch its METAR.

    For production use, swap in a full airport database.
    """
    best: Optional[tuple[str, float]] = None
    for icao, alat, alon in _AIRPORT_HINTS:
        d = _haversine_km(lat, lon, alat, alon)
        if d <= max_distance_km and (best is None or d < best[1]):
            best = (icao, d)
    if best is None:
        return None
    return fetch_metar(best[0])


def _to_float(x) -> Optional[float]:
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _to_int(x) -> Optional[int]:
    try:
        return int(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
