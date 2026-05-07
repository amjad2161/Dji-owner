"""Core type definitions used across all backends."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from math import asin, atan2, cos, degrees, radians, sin, sqrt
from typing import Optional

EARTH_RADIUS_M = 6_371_000.0


class FlightMode(str, Enum):
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

    def haversine_m(self, other: "GeoPoint") -> float:
        """Great-circle distance to another point in meters."""
        lat1, lat2 = radians(self.lat), radians(other.lat)
        dlat = lat2 - lat1
        dlon = radians(other.lon - self.lon)
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return 2 * EARTH_RADIUS_M * atan2(sqrt(a), sqrt(1 - a))

    def bearing_to(self, other: "GeoPoint") -> float:
        """Initial bearing to another point (0° = N, 90° = E)."""
        lat1, lat2 = radians(self.lat), radians(other.lat)
        dlon = radians(other.lon - self.lon)
        y = sin(dlon) * cos(lat2)
        x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
        return (degrees(atan2(y, x)) + 360) % 360

    def offset_m(self, distance_m: float, bearing_deg: float, alt_delta: float = 0.0) -> "GeoPoint":
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
        return {
            "timestamp": self.timestamp.isoformat(),
            "position": {"lat": self.position.lat, "lon": self.position.lon, "alt": self.position.alt},
            "velocity": {"forward": self.velocity_xyz[0], "right": self.velocity_xyz[1], "down": self.velocity_xyz[2]},
            "yaw": self.yaw_deg,
            "pitch": self.pitch_deg,
            "roll": self.roll_deg,
            "battery": {"percent": self.battery_percent, "voltage": self.battery_voltage},
            "gps": {"satellites": self.gps_satellites},
            "gimbal": {"pitch": self.gimbal_pitch_deg},
            "mode": self.flight_mode.value,
            "home": {"lat": self.home.lat, "lon": self.home.lon} if self.home else None,
            "motors": list(self.motor_rpm),
            "signal": self.signal_strength,
        }


@dataclass
class MissionStep:
    """One waypoint in a mission."""

    target: GeoPoint
    speed_mps: float = 5.0
    yaw_deg: Optional[float] = None  # auto = aim at next waypoint
    gimbal_pitch_deg: Optional[float] = None
    actions: list[str] = field(default_factory=list)
    hold_seconds: float = 0.0


@dataclass
class GeofenceConfig:
    """Soft and hard limits enforced by the safety layer."""

    max_radius_m: float = 500.0
    max_altitude_m: float = 120.0
    home: Optional[GeoPoint] = None
    rth_battery_threshold: int = 25
    land_battery_threshold: int = 10
    min_gps_satellites: int = 8
