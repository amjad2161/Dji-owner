"""
SkyCore - Emergency Landing Planning
Plans safe emergency landing zones based on terrain, airspace, and obstacles.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class LandingReason(str, Enum):
    """Reason for emergency landing."""
    LOW_BATTERY = "low_battery"
    GPS_LOSS = "gps_loss"
    SIGNAL_LOSS = "signal_loss"
    ENGINE_FAILURE = "engine_failure"
    WINDSPEED_EXCEEDED = "windspeed_exceeded"
    WEATHER_DETERIORATION = "weather"
    MANUAL_REQUEST = "manual"
    CUAS_THREAT = "cuas_threat"
    UNKNOWN = "unknown"


class LandingZoneType(str, Enum):
    """Type of landing zone."""
    OPEN_FIELD = "open_field"
    ROAD = "road"
    WATER = "water"
    BUILDING = "building"
    TREES = "trees"
    PARK = "park"
    HELIPAD = "helipad"
    UNKNOWN = "unknown"


@dataclass
class LandingZone:
    """A potential landing zone."""
    lat: float
    lon: float
    alt_ground_m: float
    zone_type: LandingZoneType
    size_m: float  # diameter
    safe: bool
    score: float  # 0-1, higher is better
    distance_m: float
    approach_angle_deg: float = 0.0
    obstacles: list[str] = None
    
    def __post_init__(self):
        if self.obstacles is None:
            self.obstacles = []


@dataclass
class EmergencyLandingPlan:
    """Emergency landing plan."""
    reason: LandingReason
    start_position: tuple[float, float, float]  # lat, lon, alt
    selected_zone: LandingZone
    alternative_zones: list[LandingZone]
    estimated_time_s: float
    battery_required_percent: float
    route: list[tuple[float, float, float]]  # waypoints
    warnings: list[str]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


def plan_emergency_landing(current: "GeoPoint", reason: str) -> dict:
    """
    Plan emergency landing for given position.
    
    Args:
        current: Current position (GeoPoint)
        reason: Reason for emergency landing
        
    Returns:
        Emergency landing plan dictionary
    """
    from skycore.core.types import GeoPoint
    
    # Default safe zones (in real implementation, use terrain/airspace data)
    zones = [
        LandingZone(
            lat=current.lat + 0.002,
            lon=current.lon + 0.001,
            alt_ground_m=0,
            zone_type=LandingZoneType.OPEN_FIELD,
            size_m=50,
            safe=True,
            score=0.9,
            distance_m=250,
        ),
        LandingZone(
            lat=current.lat - 0.001,
            lon=current.lon + 0.002,
            alt_ground_m=0,
            zone_type=LandingZoneType.PARK,
            size_m=40,
            safe=True,
            score=0.8,
            distance_m=300,
        ),
        LandingZone(
            lat=current.lat + 0.005,
            lon=current.lon - 0.003,
            alt_ground_m=0,
            zone_type=LandingZoneType.ROAD,
            size_m=30,
            safe=True,
            score=0.7,
            distance_m=600,
        ),
    ]
    
    # Sort by score
    zones.sort(key=lambda z: z.score, reverse=True)
    
    best = zones[0]
    
    # Calculate route
    route = [
        (current.lat, current.lon, current.alt),
        (best.lat, best.lon, best.alt_ground_m + 5),  # 5m buffer
    ]
    
    # Calculate estimated time (simplified)
    distance_m = best.distance_m
    avg_speed_mps = 5.0  # Conservative descent speed
    estimated_time_s = distance_m / avg_speed_mps + 30  # +30s for landing
    
    # Battery required (conservative estimate)
    battery_required = 20.0  # Minimum 20% reserve
    
    # Warnings based on reason
    warnings = []
    reason_enum = LandingReason(reason)
    if reason_enum == LandingReason.LOW_BATTERY:
        warnings.append("Low battery - prioritize nearest safe zone")
    elif reason_enum == LandingReason.C-UAS_THREAT:
        warnings.append("C-UAS threat detected - seek open area away from observers")
    elif reason_enum == LandingReason.GPS_LOSS:
        warnings.append("GPS unavailable - use visual landing")
        warnings.append("Compass may be unreliable - maintain visual reference")
    
    return {
        "reason": reason,
        "current_position": {"lat": current.lat, "lon": current.lon, "alt": current.alt},
        "selected_zone": {
            "lat": best.lat,
            "lon": best.lon,
            "type": best.zone_type.value,
            "distance_m": best.distance_m,
            "score": best.score,
            "safe": best.safe,
        },
        "alternatives": [
            {"lat": z.lat, "lon": z.lon, "type": z.zone_type.value, "score": z.score}
            for z in zones[1:3]
        ],
        "estimated_time_s": round(estimated_time_s, 1),
        "battery_required_percent": battery_required,
        "route": route,
        "warnings": warnings,
        "timestamp": datetime.now().isoformat(),
    }


def find_safe_landing_zones(lat: float, lon: float, radius_km: float = 5.0) -> list[dict]:
    """Find all safe landing zones within radius."""
    zones = [
        {"lat": lat + 0.01, "lon": lon + 0.01, "type": "park", "safe": True, "score": 0.9},
        {"lat": lat - 0.005, "lon": lon + 0.005, "type": "open_field", "safe": True, "score": 0.85},
        {"lat": lat + 0.02, "lon": lon - 0.015, "type": "field", "safe": True, "score": 0.8},
        {"lat": lat - 0.01, "lon": lon - 0.01, "type": "park", "safe": True, "score": 0.75},
        {"lat": lat + 0.015, "lon": lon + 0.02, "type": "helipad", "safe": True, "score": 0.95},
    ]
    return {"zones": zones, "radius_km": radius_km, "count": len(zones)}