"""
SkyCore Advanced Human-Machine Teaming v2.0
AI proposes, human approves, system executes with full transparency
"""

from typing import Dict

class AdvancedHMT:
    def __init__(self):
        self.proposals: Dict = {}

    def ai_propose_action(self, situation: str, recommendation: str, confidence: float, drone_id: str) -> Dict:
        proposal = {
            "situation": situation,
            "recommendation": recommendation,
            "confidence": confidence,
            "drone_id": drone_id,
            "status": "PENDING_HUMAN_APPROVAL"
        }
        self.proposals[drone_id] = proposal
        print(f"🧠 [HMT] AI proposes: {recommendation} (confidence: {confidence:.0%})")
        return proposal

    def human_decision(self, drone_id: str, approved: bool, operator_id: str) -> str:
        if drone_id not in self.proposals:
            return "NO_PROPOSAL"
        
        proposal = self.proposals[drone_id]
        if approved:
            proposal["status"] = "APPROVED"
            print(f"✅ [HMT] Approved by {operator_id} → Executing on {drone_id}")
            return "EXECUTE"
        else:
            proposal["status"] = "REJECTED"
            print(f"❌ [HMT] Rejected by {operator_id}")
            return "ABORT"
