"""
SkyCore Core Module
Core types, Drone ABC, and EventBus for all SkyCore implementations.
"""

from skycore.core.types import (
    GeoPoint,
    Telemetry,
    FlightMode,
    FlightStatus,
    MissionStep,
    GeofenceConfig,
    FlightRecord,
    EARTH_RADIUS_M,
)

from skycore.core.drone import Drone

from skycore.core.event_bus import EventBus, get_event_bus

__all__ = [
    # Types
    "GeoPoint",
    "Telemetry",
    "FlightMode",
    "FlightStatus",
    "MissionStep",
    "GeofenceConfig",
    "FlightRecord",
    "EARTH_RADIUS_M",
    # Core
    "Drone",
    "EventBus",
    "get_event_bus",
]