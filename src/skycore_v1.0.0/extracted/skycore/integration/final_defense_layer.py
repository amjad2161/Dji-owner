"""
SkyCore Final Defense Layer (Military Grade)
Integrates all defensive capabilities into one unstoppable (legal) system
"""

from typing import Dict
from cuas.threat_detector import ThreatDetector
from cuas.ai_classifier import AIThreatClassifier
from cuas.threat_prediction import ThreatPredictor
from cuas.defense_swarm import DefenseSwarm
from security.zero_trust import ZeroTrustSecurity
from security.drone_ids import DroneIDS
from security.immutable_audit import ImmutableAuditLog

class FinalDefenseLayer:
    def __init__(self, authorized_operator: str):
        self.operator_control = FullOperatorControl(authorized_operator)
        self.detector = ThreatDetector()
        self.classifier = AIThreatClassifier()
        self.predictor = ThreatPredictor()
        self.defense_swarm = DefenseSwarm()
        self.zero_trust = ZeroTrustSecurity()
        self.ids = DroneIDS()
        self.audit = ImmutableAuditLog()

    def process_threat(self, detection: dict, operator_id: str) -> Dict:
        # Full operator control check
        if not self.operator_control.execute_command(operator_id, {"type": "PROCESS_THREAT"}):
            return {"status": "BLOCKED", "reason": "Unauthorized operator"}

        # Full detection pipeline
        threat = self.detector.analyze_detection(detection)
        if threat:
            classified = self.classifier.classify(detection)
            predictions = self.predictor.predict([detection], [])
            
            # Log everything immutably
            self.audit.add_event("THREAT_DETECTED", {
                "threat": threat.__dict__,
                "classified": classified.__dict__
            }, operator_id)

            # Activate defensive response if needed
            if threat.threat_level in ["HIGH", "CRITICAL"]:
                self.defense_swarm.respond_to_threat(detection["position"])
                self.audit.add_event("DEFENSIVE_RESPONSE_ACTIVATED", {"threat_id": threat.drone_id}, operator_id)

            return {
                "status": "PROCESSED",
                "threat": threat,
                "classified": classified,
                "predictions": predictions,
                "defensive_action": "ACTIVATED" if threat.threat_level in ["HIGH", "CRITICAL"] else "MONITORING"
            }
        
        return {"status": "NO_THREAT"}
