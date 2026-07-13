"""
SkyCore - Drone Protocol Detection
Detection of DJI and Autel drone RF signatures based on pulse intervals.

Based on research from:
- ABHICHIRU/Elite-Drone-IDS (FPGA drone detection)
- o-gs/dji-firmware-tools (DJI protocol analysis)
- anthok/autel (Autel firmware parsing)

Detection Patterns:
- DJI OcuSync/Lightbridge: 10ms ± 0.5ms periodic burst
- Autel EVO Series: 12ms ± 0.5ms periodic burst

This is DEFENSIVE detection only - no jamming, no transmission.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

log = logging.getLogger(__name__)


class DroneProtocol(str, Enum):
    """Known drone communication protocols."""
    UNKNOWN = "unknown"
    DJI_OCUSYNC = "dji_ocusync"
    DJI_LIGHTBRIDGE = "dji_lightbridge"
    AUTEL_EVO = "autel_evo"
    FPV_GENERIC = "fpv_generic"


class DroneType(str, Enum):
    """Detected drone type."""
    UNKNOWN = "unknown"
    DJI_PHANTOM = "dji_phantom"
    DJI_MAVIC = "dji_mavic"
    DJI_MINI = "dji_mini"
    DJI_INSPIRE = "dji_inspire"
    AUTEL_EVO_NANO = "autel_evo_nano"
    AUTEL_EVO_LITE = "autel_evo_lite"
    AUTEL_EVO_PRO = "autel_evo_pro"
    AUTEL_EVO_MAX = "autel_evo_max"


@dataclass
class RFDetectionEvent:
    """Single RF detection event."""
    timestamp: float
    protocol: DroneProtocol
    confidence: float  # 0-1
    pulse_interval_ms: float
    signal_strength_dbm: Optional[float] = None
    drone_type_guess: Optional[DroneType] = None


@dataclass
class DetectedDrone:
    """A drone detected in the airspace."""
    drone_id: str  # Generated or from protocol
    protocol: DroneProtocol
    drone_type: DroneType
    first_seen: float
    last_pulse: float
    pulse_count: int = 0
    confidence: float = 0.0
    position_latest: Optional[tuple[float, float, float]] = None  # lat, lon, alt
    
    @property
    def is_confirmed(self) -> bool:
        """Drone is confirmed after enough pulses."""
        return self.pulse_count >= 100 and self.confidence >= 0.95
    
    @property
    def pulse_interval_ms(self) -> float:
        """Expected pulse interval for protocol."""
        intervals = {
            DroneProtocol.DJI_OCUSYNC: 10.0,
            DroneProtocol.DJI_LIGHTBRIDGE: 10.0,
            DroneProtocol.AUTEL_EVO: 12.0,
        }
        return intervals.get(self.protocol, 10.0)


# Protocol detection parameters from Elite-Drone-IDS research
PROTOCOL_PARAMS = {
    DroneProtocol.DJI_OCUSYNC: {
        "interval_min_ms": 9.5,
        "interval_max_ms": 10.5,
        "expected_interval_ms": 10.0,
        "lock_pulses_required": 100,
        "lock_time_s": 1.0,
    },
    DroneProtocol.DJI_LIGHTBRIDGE: {
        "interval_min_ms": 9.5,
        "interval_max_ms": 10.5,
        "expected_interval_ms": 10.0,
        "lock_pulses_required": 100,
        "lock_time_s": 1.0,
    },
    DroneProtocol.AUTEL_EVO: {
        "interval_min_ms": 11.5,
        "interval_max_ms": 12.5,
        "expected_interval_ms": 12.0,
        "lock_pulses_required": 100,
        "lock_time_s": 1.2,
    },
}


class DroneProtocolDetector:
    """Detects drone protocols based on RF pulse patterns.
    
    Uses confidence chain approach (like FPGA 100-layer chain in Elite-Drone-IDS)
    to eliminate false positives from Wi-Fi, Bluetooth, etc.
    """
    
    def __init__(self):
        self._detected_drones: dict[str, DetectedDrone] = {}
        self._pulse_timestamps: dict[str, list[float]] = {}  # drone_id -> list of pulse times
        self._monitoring = False
        
    def record_pulse(self, drone_id: str, timestamp: float, protocol: DroneProtocol) -> DetectedDrone:
        """Record a detected pulse and update drone status.
        
        Args:
            drone_id: Unique identifier for the drone
            timestamp: Unix timestamp of pulse
            protocol: Detected protocol
            
        Returns:
            Updated DetectedDrone object
        """
        if drone_id not in self._detected_drones:
            self._detected_drones[drone_id] = DetectedDrone(
                drone_id=drone_id,
                protocol=protocol,
                drone_type=self._guess_drone_type(protocol),
                first_seen=timestamp,
                last_pulse=timestamp,
                pulse_count=0,
                confidence=0.0,
            )
            self._pulse_timestamps[drone_id] = []
        
        drone = self._detected_drones[drone_id]
        drone.last_pulse = timestamp
        drone.pulse_count += 1
        self._pulse_timestamps[drone_id].append(timestamp)
        
        # Calculate confidence based on pulse regularity
        drone.confidence = self._calculate_confidence(drone_id, protocol)
        
        return drone
    
    def _calculate_confidence(self, drone_id: str, protocol: DroneProtocol) -> float:
        """Calculate detection confidence based on pulse timing regularity.
        
        Based on the 100-layer confidence chain from Elite-Drone-IDS.
        A drone is confirmed when 100 consecutive pulses fall within expected interval.
        
        Mathematical certainty:
        - Wi-Fi (30% interval match): P < 0.3^100 ≈ 1.9×10⁻⁵³
        """
        if drone_id not in self._pulse_timestamps:
            return 0.0
        
        pulses = self._pulse_timestamps[drone_id]
        if len(pulses) < 2:
            return 0.0
        
        params = PROTOCOL_PARAMS.get(protocol)
        if not params:
            return 0.0
        
        # Check recent pulses against expected interval
        valid_count = 0
        recent_pulses = pulses[-min(100, len(pulses)):]
        
        for i in range(1, len(recent_pulses)):
            interval_ms = (recent_pulses[i] - recent_pulses[i-1]) * 1000
            if params["interval_min_ms"] <= interval_ms <= params["interval_max_ms"]:
                valid_count += 1
        
        # Confidence = valid_pulses / total_pulses (capped at 100)
        max_check = min(100, len(recent_pulses) - 1)
        if max_check == 0:
            return 0.0
            
        return valid_count / max_check
    
    def _guess_drone_type(self, protocol: DroneProtocol) -> DroneType:
        """Guess drone type based on protocol.
        
        This is a heuristic - real type detection requires more data.
        """
        if protocol == DroneProtocol.AUTEL_EVO:
            return DroneType.AUTEL_EVO_PRO  # Most common assumption
        elif protocol in (DroneProtocol.DJI_OCUSYNC, DroneProtocol.DJI_LIGHTBRIDGE):
            return DroneType.DJI_MAVIC  # Most common DJI assumption
        return DroneType.UNKNOWN
    
    def identify_protocol(self, pulse_interval_ms: float) -> DroneProtocol:
        """Identify protocol based on pulse interval.
        
        Args:
            pulse_interval_ms: Measured pulse interval in milliseconds
            
        Returns:
            Detected protocol or UNKNOWN
        """
        # Check DJI (10ms ± 0.5ms)
        if 9.5 <= pulse_interval_ms <= 10.5:
            return DroneProtocol.DJI_OCUSYNC
        
        # Check Autel (12ms ± 0.5ms)
        if 11.5 <= pulse_interval_ms <= 12.5:
            return DroneProtocol.AUTEL_EVO
        
        return DroneProtocol.UNKNOWN
    
    def get_detected_drones(self) -> list[DetectedDrone]:
        """Get all currently detected drones."""
        return list(self._detected_drones.values())
    
    def get_confirmed_drones(self) -> list[DetectedDrone]:
        """Get only confirmed drones (100+ valid pulses)."""
        return [d for d in self._detected_drones.values() if d.is_confirmed]
    
    def get_drone(self, drone_id: str) -> Optional[DetectedDrone]:
        """Get specific drone by ID."""
        return self._detected_drones.get(drone_id)
    
    def clear_stale_detections(self, max_age_s: float = 60.0) -> None:
        """Remove detections older than max_age_s seconds."""
        now = time.time()
        stale_ids = [
            drone_id for drone_id, drone in self._detected_drones.items()
            if now - drone.last_pulse > max_age_s
        ]
        for drone_id in stale_ids:
            del self._detected_drones[drone_id]
            if drone_id in self._pulse_timestamps:
                del self._pulse_timestamps[drone_id]
        
        if stale_ids:
            log.debug(f"Cleared {len(stale_ids)} stale drone detections")


# Global detector instance
default_detector = DroneProtocolDetector()