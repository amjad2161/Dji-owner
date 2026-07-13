"""
SkyCore Multi-Domain Coordination (Air + Ground + Sea)
Coordinates different types of unmanned systems
"""

from typing import Dict, List

class MultiDomainCoordinator:
    def __init__(self):
        self.assets: Dict[str, dict] = {}

    def register_asset(self, asset_id: str, domain: str, capabilities: List[str]):
        self.assets[asset_id] = {"domain": domain, "capabilities": capabilities}
        print(f"🌐 [Multi-Domain] Registered {asset_id} ({domain})")

    def coordinate_mission(self, mission_type: str, primary_domain: str):
        print(f"🎯 [Multi-Domain] Coordinating {mission_type} across domains...")
        for asset_id, info in self.assets.items():
            if info["domain"] != primary_domain:
                print(f"   → {asset_id} ({info['domain']}) supporting")
