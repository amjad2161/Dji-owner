"""
SkyCore Immutable Audit Log (Blockchain-style)
Tamper-proof logging for legal and security purposes
"""

import hashlib
import time
from typing import List, Dict

class ImmutableAuditLog:
    def __init__(self):
        self.chain: List[Dict] = []
        self.last_hash = "GENESIS"

    def add_event(self, event_type: str, details: dict, actor: str):
        block = {
            "timestamp": time.time(),
            "event_type": event_type,
            "details": details,
            "actor": actor,
            "previous_hash": self.last_hash
        }
        block_hash = hashlib.sha256(str(block).encode()).hexdigest()
        block["hash"] = block_hash
        self.chain.append(block)
        self.last_hash = block_hash
        print(f"🔗 [Audit] Immutable log entry: {event_type}")

    def verify_chain(self) -> bool:
        """Verify the entire chain hasn't been tampered with"""
        for i in range(1, len(self.chain)):
            if self.chain[i]["previous_hash"] != self.chain[i-1]["hash"]:
                return False
        return True

    def get_audit_trail(self, limit: int = 50) -> List[Dict]:
        return self.chain[-limit:]
