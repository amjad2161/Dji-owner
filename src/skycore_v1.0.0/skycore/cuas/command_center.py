"""
SkyCore Command Center Integration
Professional alerting and logging for security forces
"""

from datetime import datetime
from typing import List
from cuas.threat_detector import Threat

class CommandCenter:
    def __init__(self, unit_name: str = "Security Command"):
        self.unit_name = unit_name
        self.alert_log = []

    def send_alert(self, threat: Threat, priority: str = "HIGH"):
        alert = {
            "timestamp": datetime.now(),
            "unit": self.unit_name,
            "threat_id": threat.drone_id,
            "threat_level": threat.threat_level,
            "position": threat.position,
            "altitude": threat.altitude,
            "recommended_action": threat.recommended_action,
            "priority": priority
        }
        self.alert_log.append(alert)
        print(f"🚨 [{priority}] ALERT to {self.unit_name}: {threat.classification} at {threat.position} | Action: {threat.recommended_action}")

    def generate_daily_report(self) -> str:
        return f"Daily Report for {self.unit_name} - {len(self.alert_log)} threats logged today"
