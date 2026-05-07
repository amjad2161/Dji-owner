"""Manned-aircraft awareness via OpenSky Network.

https://opensky-network.org/api is a free public ADS-B aggregator. We
query a bounding box around the drone's location and surface any aircraft
at altitudes that overlap typical drone operating ceilings.

Use this **before** flight to check for traffic and **during** flight as a
soft warning. It is not a substitute for visual line-of-sight or formal
DAA equipment.

Rate limits: 100 requests/day anonymous, 4000/day authenticated. Default
use case (one query at preflight + occasional during flight) fits easily.
"""
from __future__ import annotations

import json
import logging
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

from skycore.core.types import GeoPoint

log = logging.getLogger(__name__)

OPENSKY_URL = "https://opensky-network.org/api/states/all"


@dataclass
class Aircraft:
    icao24: str
    callsign: Optional[str]
    origin_country: Optional[str]
    longitude: Optional[float]
    latitude: Optional[float]
    baro_altitude_m: Optional[float]
    geo_altitude_m: Optional[float]
    on_ground: bool
    velocity_mps: Optional[float]
    heading_deg: Optional[float]
    vertical_rate_mps: Optional[float]

    def position(self) -> Optional[GeoPoint]:
        if self.latitude is None or self.longitude is None:
            return None
        alt = self.geo_altitude_m or self.baro_altitude_m or 0.0
        return GeoPoint(self.latitude, self.longitude, alt)


class OpenSkyClient:
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None, timeout_s: float = 10.0):
        self.username = username
        self.password = password
        self.timeout_s = timeout_s

    def _bbox_around(self, center: GeoPoint, radius_km: float) -> tuple[float, float, float, float]:
        """Return (lamin, lamax, lomin, lomax) bounding box."""
        deg_lat = radius_km / 111.0
        deg_lon = radius_km / (111.0 * max(0.05, math.cos(math.radians(center.lat))))
        return (
            center.lat - deg_lat,
            center.lat + deg_lat,
            center.lon - deg_lon,
            center.lon + deg_lon,
        )

    def states_in_bbox(self, lamin: float, lamax: float, lomin: float, lomax: float) -> list[Aircraft]:
        params = {"lamin": lamin, "lamax": lamax, "lomin": lomin, "lomax": lomax}
        req = urllib.request.Request(f"{OPENSKY_URL}?{urllib.parse.urlencode(params)}")
        if self.username:
            import base64
            creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            req.add_header("Authorization", f"Basic {creds}")
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        states = data.get("states") or []
        out: list[Aircraft] = []
        for s in states:
            try:
                out.append(
                    Aircraft(
                        icao24=s[0],
                        callsign=(s[1] or "").strip() or None,
                        origin_country=s[2],
                        longitude=s[5],
                        latitude=s[6],
                        baro_altitude_m=s[7],
                        on_ground=bool(s[8]),
                        velocity_mps=s[9],
                        heading_deg=s[10],
                        vertical_rate_mps=s[11],
                        geo_altitude_m=s[13],
                    )
                )
            except (IndexError, TypeError):
                continue
        return out

    def near(self, center: GeoPoint, radius_km: float = 10.0) -> list[Aircraft]:
        """All aircraft within radius_km of center."""
        bbox = self._bbox_around(center, radius_km)
        states = self.states_in_bbox(*bbox)
        out = []
        for a in states:
            pos = a.position()
            if pos and center.haversine_m(pos) <= radius_km * 1000:
                out.append(a)
        return out


def nearby_aircraft(center: GeoPoint, radius_km: float = 10.0) -> list[Aircraft]:
    """Convenience: anonymous query for aircraft within radius_km."""
    return OpenSkyClient().near(center, radius_km)


def is_traffic_concern(
    drone_position: GeoPoint,
    drone_alt_amsl_m: float,
    radius_km: float = 5.0,
    altitude_band_m: float = 200.0,
    aircraft: Optional[list[Aircraft]] = None,
) -> tuple[bool, list[Aircraft]]:
    """Check whether any aircraft is within radius_km AND altitude_band_m.

    Returns (any_concern, list_of_concerning_aircraft).
    """
    if aircraft is None:
        aircraft = nearby_aircraft(drone_position, radius_km=radius_km)
    concerning = []
    for a in aircraft:
        if a.on_ground:
            continue
        pos = a.position()
        if pos is None:
            continue
        h = drone_position.haversine_m(pos)
        a_alt = a.geo_altitude_m or a.baro_altitude_m or 0
        v = abs(drone_alt_amsl_m - a_alt)
        if h <= radius_km * 1000 and v <= altitude_band_m:
            concerning.append(a)
    return bool(concerning), concerning
