"""
SkyCore Autonomous Recharging Stations
Inspired by Israeli + US military systems
"""

from typing import Dict, List

class AutonomousRecharging:
    def __init__(self):
        self.stations: Dict[str, dict] = {}

    def register_station(self, station_id: str, position: tuple, capacity: int):
        self.stations[station_id] = {
            "position": position,
            "capacity": capacity,
            "occupied": 0
        }
        print(f"🔋 [Recharge] Station {station_id} registered at {position}")

    def assign_drone(self, drone_id: str, current_battery: int) -> str:
        if current_battery > 30:
            return "NO_NEED"
        
        for station_id, info in self.stations.items():
            if info["occupied"] < info["capacity"]:
                info["occupied"] += 1
                print(f"🔋 [Recharge] {drone_id} assigned to {station_id}")
                return station_id
        
        return "NO_STATION_AVAILABLE"
