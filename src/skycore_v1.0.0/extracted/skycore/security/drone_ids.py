"""
SkyCore Drone Intrusion Detection System (IDS)
Detects anomalous behavior, tampering, and cyber attacks on drones
"""

from typing import Dict, List
from dataclasses import dataclass

@dataclass
class SecurityEvent:
    drone_id: str
    event_type: str  # "Anomaly", "Tamper", "Unauthorized_Access", "Malware"
    severity: str
    details: str
    timestamp: float

class DroneIDS:
    def __init__(self):
        self.events: List[SecurityEvent] = []
        self.baseline: Dict[str, dict] = {}

    def learn_baseline(self, drone_id: str, normal_behavior: dict):
        self.baseline[drone_id] = normal_behavior
        print(f"📊 [IDS] Baseline learned for {drone_id}")

    def detect_anomaly(self, drone_id: str, current_behavior: dict) -> List[SecurityEvent]:
        events = []
        if drone_id not in self.baseline:
            return events

        baseline = self.baseline[drone_id]
        
        # Check for anomalies
        if current_behavior.get("cpu_usage", 0) > baseline.get("cpu_usage", 50) * 1.5:
            events.append(SecurityEvent(drone_id, "Anomaly", "HIGH", "Unusual CPU usage", time.time()))
        
        if current_behavior.get("unexpected_command", False):
            events.append(SecurityEvent(drone_id, "Unauthorized_Access", "CRITICAL", "Unexpected command received", time.time()))
        
        self.events.extend(events)
        return events

    def get_critical_events(self) -> List[SecurityEvent]:
        return [e for e in self.events if e.severity == "CRITICAL"]
