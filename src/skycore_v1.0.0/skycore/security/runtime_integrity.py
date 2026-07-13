"""
SkyCore Runtime Integrity Monitoring
Real-time detection of tampering, rootkits, or unauthorized changes on drones
"""

from typing import Dict
import hashlib

class RuntimeIntegrityMonitor:
    def __init__(self):
        self.baselines: Dict[str, str] = {}

    def set_baseline(self, drone_id: str, system_hash: str):
        self.baselines[drone_id] = system_hash
        print(f"📊 [Integrity] Baseline set for {drone_id}")

    def check_integrity(self, drone_id: str, current_hash: str) -> bool:
        if drone_id not in self.baselines:
            return False
        
        if current_hash != self.baselines[drone_id]:
            print(f"🚨 [Integrity] TAMPERING DETECTED on {drone_id}!")
            return False
        return True
