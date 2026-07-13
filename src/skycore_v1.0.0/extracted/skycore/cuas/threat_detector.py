"""
SkyCore Counter-UAS Threat Detector
Professional-grade unauthorized drone detection for security forces
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class Threat:
    drone_id: str
    classification: str  # "Unknown", "Commercial", "FPV", "Military"
    position: tuple
    altitude: float
    speed: float
    threat_level: str  # LOW / MEDIUM / HIGH / CRITICAL
    confidence: float
    timestamp: datetime
    recommended_action: str

class ThreatDetector:
    def __init__(self):
        self.known_threats = []
        self.alert_threshold = 0.7

    def analyze_detection(self, detection: dict) -> Optional[Threat]:
        """Analyze a detection and return threat assessment"""
        speed = detection.get('speed', 0)
        alt = detection.get('altitude', 0)
        size = detection.get('size', 'small')
        
        threat_level = "LOW"
        confidence = 0.6
        action = "Monitor"
        
        if speed > 25 or alt < 20:
            threat_level = "HIGH"
            confidence = 0.85
            action = "Alert Command Center + Track"
        elif speed > 15:
            threat_level = "MEDIUM"
            confidence = 0.75
            action = "Track and Log"
        
        return Threat(
            drone_id=detection.get('id', 'UNKNOWN'),
            classification=detection.get('type', 'Unknown Drone'),
            position=detection.get('position', (0,0)),
            altitude=alt,
            speed=speed,
            threat_level=threat_level,
            confidence=confidence,
            timestamp=datetime.now(),
            recommended_action=action
        )

    def get_active_threats(self) -> List[Threat]:
        return [t for t in self.known_threats if t.threat_level in ["HIGH", "CRITICAL"]]
