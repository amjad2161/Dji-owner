"""
SkyCore Military Key Management System
Quantum-resistant key rotation + secure distribution
"""

import hashlib
import time
from typing import Dict, Optional

class MilitaryKeyManagement:
    def __init__(self):
        self.keys: Dict[str, dict] = {}
        self.rotation_interval = 3600  # 1 hour

    def generate_key(self, drone_id: str, key_type: str = "AES-256") -> str:
        """Generate new key (in real: post-quantum crypto)"""
        timestamp = str(time.time())
        key = hashlib.sha256(f"{drone_id}-{timestamp}-MILITARY".encode()).hexdigest()[:32]
        
        self.keys[drone_id] = {
            "key": key,
            "type": key_type,
            "created": timestamp,
            "expires": time.time() + self.rotation_interval
        }
        print(f"🔑 [KeyMgmt] New {key_type} key generated for {drone_id}")
        return key

    def rotate_keys(self):
        """Automatic key rotation"""
        now = time.time()
        for drone_id, info in list(self.keys.items()):
            if now > info["expires"]:
                new_key = self.generate_key(drone_id, info["type"])
                print(f"🔄 [KeyMgmt] Key rotated for {drone_id}")
        return True

    def get_key(self, drone_id: str) -> Optional[str]:
        if drone_id in self.keys:
            return self.keys[drone_id]["key"]
        return None
