"""
SkyCore Awareness - ADS-B & Manned Aircraft Detection

Real-time monitoring of manned aircraft via OpenSky Network and local ADS-B receivers.
Integrates with OpenSky API for comprehensive airspace awareness.

Capabilities:
- Real-time aircraft tracking
- Collision avoidance alerts
- Priority airspace detection
- Flight path prediction
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

OPENSKY_URL = "https://opensky-network.org/api/states/all"


@dataclass
class AircraftContact:
    """ADS-B tracked aircraft."""
    icao24: str
    callsign: Optional[str]
    origin_country: str
    lat: float
    lon: float
    altitude_m: float  # barometric altitude in meters
    velocity_mps: Optional[float]
    heading_deg: Optional[float]
    vertical_rate_mps: Optional[float]
    on_ground: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def position(self) -> tuple[float, float, float]:
        return (self.lat, self.lon, self.altitude_m)

    @property
    def is_military(self) -> bool:
        """Guess if aircraft might be military based on callsign patterns."""
        if not self.callsign:
            return False
        # Common military prefixes
        military_prefixes = ["AF", "Army", "Navy", "RAF", "USAF", "VFR"]
        return any(self.callsign.startswith(p) for p in military_prefixes)


@dataclass
class AirspaceAlert:
    """Alert for potential conflict with manned aircraft."""
    aircraft: AircraftContact
    distance_m: float
    time_to_closest_approach_s: float
    altitude_separation_m: float
    threat_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    recommended_action: str


class AirspaceMonitor:
    """Monitor airspace for manned aircraft using ADS-B."""

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        poll_interval_s: float = 10.0,
    ):
        self.username = username
        self.password = password
        self.poll_interval_s = poll_interval_s
        self._contacts: dict[str, AircraftContact] = {}
        self._task: Optional[asyncio.Task] = None
        self._listeners: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to airspace updates."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._listeners:
            self._listeners.remove(q)

    async def start(self, center_lat: float, center_lon: float, radius_km: float = 50.0) -> None:
        """Start monitoring airspace around a location."""
        self._task = asyncio.create_task(self._monitor_loop(center_lat, center_lon, radius_km))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self, center_lat: float, center_lon: float, radius_km: float) -> None:
        """Main monitoring loop."""
        while True:
            try:
                await self._fetch_and_update(center_lat, center_lon, radius_km)
                await asyncio.sleep(self.poll_interval_s)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning("Airspace monitor error: %s", e)
                await asyncio.sleep(self.poll_interval_s * 2)

    async def _fetch_and_update(self, center_lat: float, center_lon: float, radius_km: float) -> None:
        """Fetch ADS-B data and update contacts."""
        contacts = await self._fetch_opensky(center_lat, center_lon, radius_km)
        
        # Update internal state
        for c in contacts:
            self._contacts[c.icao24] = c

        # Remove stale contacts (no update in 60s)
        now = datetime.utcnow()
        stale = [
            icao for icao, c in self._contacts.items()
            if (now - c.timestamp).total_seconds() > 60
        ]
        for icao in stale:
            del self._contacts[icao]

        # Notify listeners
        for listener in self._listeners:
            try:
                listener.put_nowait(contacts)
            except asyncio.QueueFull:
                log.warning("Airspace listener queue full")

    async def _fetch_opensky(
        self,
        center_lat: float,
        center_lon: float,
        radius_km: float,
    ) -> list[AircraftContact]:
        """Fetch from OpenSky Network API."""
        # Calculate bounding box
        deg_lat = radius_km / 111.0
        deg_lon = radius_km / (111.0 * max(0.01, abs(math.cos(math.radians(center_lat)))))

        lamin = center_lat - deg_lat
        lamax = center_lat + deg_lat
        lomin = center_lon - deg_lon
        lomax = center_lon + deg_lon

        params = f"lamin={lamin}&lamax={lamax}&lomin={lomin}&lomax={lomax}"
        req_url = f"{OPENSKY_URL}?{params}"

        import urllib.request
        req = urllib.request.Request(req_url)

        if self.username:
            import base64
            creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            req.add_header("Authorization", f"Basic {creds}")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            log.warning("OpenSky fetch failed: %s", e)
            return []

        states = data.get("states") or []
        contacts = []

        for s in states:
            try:
                if len(s) < 14:
                    continue

                contact = AircraftContact(
                    icao24=s[0],
                    callsign=s[1].strip() or None if s[1] else None,
                    origin_country=s[2] or "Unknown",
                    lat=float(s[5]) if s[5] else 0,
                    lon=float(s[6]) if s[6] else 0,
                    altitude_m=float(s[7]) if s[7] else 0,
                    velocity_mps=float(s[9]) if s[9] else None,
                    heading_deg=float(s[10]) if s[10] else None,
                    vertical_rate_mps=float(s[11]) if s[11] else None,
                    on_ground=bool(s[8]),
                )
                contacts.append(contact)
            except (IndexError, TypeError, ValueError):
                continue

        return contacts

    def get_nearby(self, lat: float, lon: float, altitude_m: float, radius_m: float = 3000) -> list[AirspaceAlert]:
        """Get aircraft within radius that could conflict with drone."""
        alerts = []
        drone_alt = altitude_m

        for icao, contact in self._contacts.items():
            if contact.on_ground:
                continue

            # Calculate horizontal distance
            dist_m = self._haversine_m(lat, lon, contact.lat, contact.lon)

            if dist_m > radius_m:
                continue

            # Calculate altitude separation
            alt_sep = abs(drone_alt - contact.altitude_m)

            # Determine threat level
            if dist_m < 500 and alt_sep < 150:
                threat = "CRITICAL"
            elif dist_m < 1000 and alt_sep < 300:
                threat = "HIGH"
            elif dist_m < 2000 and alt_sep < 500:
                threat = "MEDIUM"
            else:
                threat = "LOW"

            # Time to closest approach (simplified)
            if contact.velocity_mps:
                time_s = dist_m / max(contact.velocity_mps, 1)
            else:
                time_s = 60  # Assume approach if no velocity data

            if threat != "LOW":
                alerts.append(AirspaceAlert(
                    aircraft=contact,
                    distance_m=dist_m,
                    time_to_closest_approach_s=time_s,
                    altitude_separation_m=alt_sep,
                    threat_level=threat,
                    recommended_action=self._get_action(threat, contact),
                ))

        # Sort by threat level and distance
        alerts.sort(key=lambda a: (
            {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}[a.threat_level],
            a.distance_m,
        ))

        return alerts

    def _haversine_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance in meters."""
        R = 6371000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def _get_action(self, threat: str, contact: AircraftContact) -> str:
        """Get recommended action based on threat level."""
        if threat == "CRITICAL":
            return "Immediate hover and await separation"
        elif threat == "HIGH":
            return f"Alert operator, maintain {contact.callsign or 'traffic'} awareness"
        elif threat == "MEDIUM":
            return "Monitor traffic, be ready to adjust altitude"
        else:
            return "Standard operations, no action required"

    def get_all_contacts(self) -> list[AircraftContact]:
        """Get all currently tracked aircraft."""
        return list(self._contacts.values())


# Global singleton for use across the application
default_monitor = AirspaceMonitor()


async def quick_airspace_check(lat: float, lon: float, radius_km: float = 10.0) -> list[dict]:
    """Quick one-shot airspace check. Returns list of aircraft dicts."""
    monitor = AirspaceMonitor()
    await monitor._fetch_and_update(lat, lon, radius_km)
    return [
        {
            "icao": c.icao24,
            "callsign": c.callsign,
            "country": c.origin_country,
            "lat": c.lat,
            "lon": c.lon,
            "alt_m": c.altitude_m,
            "speed_mps": c.velocity_mps,
            "heading_deg": c.heading_deg,
        }
        for c in monitor._contacts.values()
    ]