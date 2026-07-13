"""
SkyCore Autonomous Threat Response v1.0
AI makes decisions without human intervention (Level 10+)
"""

from typing import Dict, Optional
from cuas.threat_detector import Threat
from cuas.defense_swarm import DefenseSwarm
from cuas.counter_swarm import CounterSwarm

class AutonomousThreatResponse:
    def __init__(self):
        self.defense_swarm = DefenseSwarm()
        self.counter_swarm = CounterSwarm()
        self.autonomous_mode = True  # AI decides alone
    
    async def evaluate_and_respond(self, threat: Threat) -> Dict:
        """
        AI evaluates threat and responds autonomously
        No human approval needed for defensive actions
        """
        if not self.autonomous_mode:
            return {"status": "MANUAL_MODE", "action": "NONE"}
        
        response = {
            "threat_id": threat.drone_id,
            "threat_level": threat.threat_level,
            "autonomous_decision": "",
            "actions_taken": []
        }
        
        if threat.threat_level == "CRITICAL":
            # Immediate autonomous response
            await self.defense_swarm.respond_to_threat(threat.position, friendly_drones=6)
            response["autonomous_decision"] = "IMMEDIATE_DEFENSIVE_SWARM"
            response["actions_taken"].append("Defensive Swarm (6 drones)")
            
            if threat.speed > 30:
                await self.counter_swarm.activate_countermeasures(1)
                response["actions_taken"].append("Counter-Swarm + EW")
        
        elif threat.threat_level == "HIGH":
            await self.defense_swarm.respond_to_threat(threat.position, friendly_drones=4)
            response["autonomous_decision"] = "DEFENSIVE_SWARM"
            response["actions_taken"].append("Defensive Swarm (4 drones)")
        
        elif threat.threat_level == "MEDIUM":
            response["autonomous_decision"] = "MONITOR_AND_ALERT"
            response["actions_taken"].append("Increased surveillance")
        
        else:
            response["autonomous_decision"] = "LOG_ONLY"
        
        return response
