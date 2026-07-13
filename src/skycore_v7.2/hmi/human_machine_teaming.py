"""
SkyCore Human-Machine Teaming (HMT) Interface
Seamless collaboration between human operators and AI/autonomous systems
"""

from typing import Dict, Callable

class HumanMachineTeaming:
    def __init__(self):
        self.operators: Dict[str, dict] = {}
        self.ai_confidence_threshold = 0.85

    def register_operator(self, operator_id: str, role: str):
        self.operators[operator_id] = {"role": role, "status": "active"}
        print(f"👤 [HMT] Operator {operator_id} ({role}) connected")

    def request_human_decision(self, situation: str, ai_recommendation: str, confidence: float) -> str:
        if confidence >= self.ai_confidence_threshold:
            return "AUTO_EXECUTE"
        else:
            print(f"🧠 [HMT] Low confidence ({confidence:.2f}). Requesting human decision...")
            print(f"   Situation: {situation}")
            print(f"   AI recommends: {ai_recommendation}")
            return "HUMAN_REVIEW_REQUIRED"

    def execute_with_human_oversight(self, action: str, operator_id: str) -> bool:
        if operator_id in self.operators:
            print(f"✅ [HMT] {action} executed under human oversight ({operator_id})")
            return True
        return False
