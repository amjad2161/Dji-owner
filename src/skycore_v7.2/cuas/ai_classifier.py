"""
SkyCore AI Threat Classifier
Advanced classification using simple ML rules + confidence scoring
"""

from dataclasses import dataclass
from typing import Dict

@dataclass
class ClassifiedThreat:
    drone_type: str
    threat_category: str  # Recreational / Commercial / Weaponized / Surveillance
    risk_score: float  # 0-100
    recommended_response: str

class AIThreatClassifier:
    def classify(self, detection: Dict) -> ClassifiedThreat:
        speed = detection.get('speed', 0)
        alt = detection.get('altitude', 0)
        size = detection.get('size', 'small')
        behavior = detection.get('behavior', 'normal')
        
        if speed > 30 and alt < 30:
            return ClassifiedThreat("FPV Racing / Weaponized", "Weaponized", 92, "Immediate intercept + alert")
        elif speed > 20 and behavior == "loitering":
            return ClassifiedThreat("Surveillance Drone", "Surveillance", 78, "Track + investigate")
        elif size == "large":
            return ClassifiedThreat("Commercial / Military", "Commercial", 65, "Monitor and log")
        else:
            return ClassifiedThreat("Recreational / Unknown", "Recreational", 45, "Log and observe")
