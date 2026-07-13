"""
SkyCore - Protocol Integration Module
Unified interface for drone protocol detection and flight log analysis.

Based on research from 40+ GitHub repos:
- DJI/OcuSync protocols (10ms pulse interval)
- Autel EVO protocols (12ms pulse interval)
- Flight log formats (DJI TXT/DAT, Litchi CSV, Airdata, Autel)
- Security considerations for airspace awareness
"""

from __future__ import annotations

from protocol.drone_detector import (
    DroneProtocolDetector,
    DroneProtocol,
    DroneType,
    DetectedDrone,
    RFDetectionEvent,
    default_detector,
)

from protocol.flight_log_parser import (
    FlightLogParser,
    FlightLog,
    FlightLogHeader,
    TelemetryPoint,
    LogFormat,
    parse_flight_log,
    default_parser,
)

__all__ = [
    # Detection
    "DroneProtocolDetector",
    "DroneProtocol",
    "DroneType", 
    "DetectedDrone",
    "RFDetectionEvent",
    "default_detector",
    # Log parsing
    "FlightLogParser",
    "FlightLog",
    "FlightLogHeader",
    "TelemetryPoint",
    "LogFormat",
    "parse_flight_log",
    "default_parser",
]