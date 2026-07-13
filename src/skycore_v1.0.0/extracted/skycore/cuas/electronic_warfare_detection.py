"""
SkyCore Electronic Warfare Detection (Legal Detection Only)
Detects jamming, spoofing, and GPS denial attempts (no active jamming)
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class EWEvent:
    event_type: str  # "Jamming", "Spoofing", "GPS_Denial"
    severity: str
    affected_drones: list
    recommended_action: str

class ElectronicWarfareDetector:
    def detect_jamming(self, signal_data: dict) -> Optional[EWEvent]:
        if signal_data.get("noise_level", 0) > 0.8:
            return EWEvent(
                event_type="Jamming",
                severity="HIGH",
                affected_drones=["ALL"],
                recommended_action="Switch to backup frequencies + alert command"
            )
        return None

    def detect_spoofing(self, gps_data: dict) -> Optional[EWEvent]:
        if gps_data.get("position_jump", False):
            return EWEvent(
                event_type="Spoofing",
                severity="CRITICAL",
                affected_drones=[gps_data.get("drone_id")],
                recommended_action="Ignore GPS + use visual/INS navigation"
            )
        return None

    def detect_gps_denial(self, satellite_count: int) -> Optional[EWEvent]:
        if satellite_count < 4:
            return EWEvent(
                event_type="GPS_Denial",
                severity="HIGH",
                affected_drones=["ALL"],
                recommended_action="Activate INS backup + reduce mission scope"
            )
        return None
