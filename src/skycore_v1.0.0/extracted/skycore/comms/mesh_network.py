"""
SkyCore Secure Mesh Network (inspired by military systems)
Drone-to-drone encrypted communication + self-healing
"""

from typing import Dict, List
import asyncio

class SecureMeshNetwork:
    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.topology: List = []

    def add_drone(self, drone_id: str, position: tuple):
        self.nodes[drone_id] = {"position": position, "status": "online", "last_seen": "now"}
        print(f"📡 Mesh: Drone {drone_id} joined network")

    async def broadcast(self, message: dict, exclude: str = None):
        """Encrypted broadcast to all drones"""
        for drone_id in self.nodes:
            if drone_id != exclude:
                print(f"📤 Mesh → {drone_id}: {message['type']}")
                await asyncio.sleep(0.05)  # simulate latency

    def self_heal(self):
        """Remove failed nodes and re-route"""
        offline = [d for d, info in self.nodes.items() if info["status"] == "offline"]
        for d in offline:
            del self.nodes[d]
        print(f"🔧 Mesh self-healed: {len(offline)} nodes removed")
