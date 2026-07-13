"""
SkyCore Core - Type Definitions
All shared data types for SkyCore platform
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from math import asin, atan2, cos, degrees, radians, sin, sqrt
from typing import Optional

EARTH_RADIUS_M = 6_371_000.0


class FlightMode(str, Enum):
    """Flight mode enumeration."""
    GROUND = "ground"
    TAKEOFF = "takeoff"
    HOVER = "hover"
    POSITION = "position"
    SPORT = "sport"
    MISSION = "mission"
    RTH = "rth"
    LANDING = "landing"
    EMERGENCY = "emergency"


class FlightStatus(str, Enum):
    """Flight status enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ARMED = "armed"
    FLYING = "flying"
    LANDED = "landed"
    ERROR = "error"


@dataclass(frozen=True)
class GeoPoint:
    """Geographic point. Altitude is meters above takeoff (relative)."""
    lat: float
    lon: float
    alt: float = 0.0

    def __post_init__(self) -> None:
        if not -90 <= self.lat <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {self.lat}")
        if not -180 <= self.lon <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {self.lon}")

    def haversine_m(self, other: GeoPoint) -> float:
        """Great-circle distance to another point in meters."""
        lat1, lat2 = radians(self.lat), radians(other.lat)
        dlat = lat2 - lat1
        dlon = radians(other.lon - self.lon)
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return 2 * EARTH_RADIUS_M * atan2(sqrt(a), sqrt(1 - a))

    def bearing_to(self, other: GeoPoint) -> float:
        """Initial bearing to another point (0° = N, 90° = E)."""
        lat1, lat2 = radians(self.lat), radians(other.lat)
        dlon = radians(other.lon - self.lon)
        y = sin(dlon) * cos(lat2)
        x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
        return (degrees(atan2(y, x)) + 360) % 360

    def offset_m(self, distance_m: float, bearing_deg: float, alt_delta: float = 0.0) -> GeoPoint:
        """Return a new point offset by distance + bearing."""
        br = radians(bearing_deg)
        d_R = distance_m / EARTH_RADIUS_M
        lat1 = radians(self.lat)
        lon1 = radians(self.lon)
        lat2 = asin(sin(lat1) * cos(d_R) + cos(lat1) * sin(d_R) * cos(br))
        lon2 = lon1 + atan2(
            sin(br) * sin(d_R) * cos(lat1),
            cos(d_R) - sin(lat1) * sin(lat2),
        )
        return GeoPoint(degrees(lat2), degrees(lon2), self.alt + alt_delta)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {"lat": self.lat, "lon": self.lon, "alt": self.alt}
    
    @classmethod
    def from_dict(cls, d: dict) -> GeoPoint:
        """Create from dictionary."""
        return cls(lat=d["lat"], lon=d["lon"], alt=d.get("alt", 0.0))


@dataclass
class Telemetry:
    """A single telemetry frame."""
    timestamp: datetime
    position: GeoPoint
    velocity_xyz: tuple[float, float, float]  # m/s, body frame: forward, right, down
    yaw_deg: float
    pitch_deg: float
    roll_deg: float
    battery_percent: float
    battery_voltage: float
    gps_satellites: int
    gimbal_pitch_deg: float
    flight_mode: FlightMode
    home: Optional[GeoPoint] = None
    motor_rpm: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    signal_strength: int = 100  # 0-100

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "position": self.position.to_dict() if self.position else None,
            "velocity_xyz": self.velocity_xyz,
            "yaw_deg": self.yaw_deg,
            "pitch_deg": self.pitch_deg,
            "roll_deg": self.roll_deg,
            "battery_percent": self.battery_percent,
            "battery_voltage": self.battery_voltage,
            "gps_satellites": self.gps_satellites,
            "gimbal_pitch_deg": self.gimbal_pitch_deg,
            "flight_mode": self.flight_mode.value if isinstance(self.flight_mode, Enum) else str(self.flight_mode),
            "home": self.home.to_dict() if self.home else None,
            "motor_rpm": self.motor_rpm,
            "signal_strength": self.signal_strength,
        }


@dataclass
class MissionStep:
    """A single waypoint in a mission."""
    point: GeoPoint
    speed_mps: float = 5.0
    heading_deg: Optional[float] = None
    gimbal_pitch_deg: Optional[float] = None
    hover_s: float = 0.0  # seconds to hover at waypoint


@dataclass
class GeofenceConfig:
    """Geofence boundary configuration."""
    home: GeoPoint
    max_altitude_m: float = 120.0  # regulatory 400ft
    max_distance_m: float = 500.0  # from home
    no_fly_zones: list[GeoPoint] = field(default_factory=list)
    # Battery thresholds
    land_battery_threshold: float = 15.0  # Emergency land below this
    rth_battery_threshold: float = 25.0  # Return to home below this
    min_gps_satellites: int = 8  # Minimum GPS for safe flight
    
    def contains(self, point: GeoPoint) -> bool:
        """Check if point is within geofence."""
        # Check altitude
        if point.alt > self.max_altitude_m:
            return False
        # Check distance
        if self.home.haversine_m(point) > self.max_distance_m:
            return False
        return True


@dataclass
class FlightRecord:
    """Complete flight record for storage."""
    start_time: datetime
    end_time: Optional[datetime] = None
    home: Optional[GeoPoint] = None
    telemetry: list[Telemetry] = field(default_factory=list)
    mission: list[MissionStep] = field(default_factory=list)
    notes: str = ""
    
    @property
    def duration_s(self) -> Optional[float]:
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def max_altitude_m(self) -> Optional[float]:
        if not self.telemetry:
            return None
        return max(t.position.alt for t in self.telemetry)
    
    @property
    def total_distance_m(self) -> Optional[float]:
        if len(self.telemetry) < 2:
            return None
        total = 0.0
        for i in range(1, len(self.telemetry)):
            total += self.telemetry[i-1].position.haversine_m(self.telemetry[i].position)
        return total