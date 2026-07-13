"""
SkyCore Persistent Surveillance (Legal)
24/7 coverage with automatic drone rotation
"""

import asyncio
from typing import List
from core.drone import Drone

class PersistentSurveillance:
    def __init__(self, drones: List[Drone]):
        self.drones = drones
        self.active = False

    async def start(self, poi: tuple, duration_hours: int = 24):
        self.active = True
        print(f"📡 Starting persistent surveillance over {poi} for {duration_hours}h")
        
        current_drone = 0
        while self.active:
            drone = self.drones[current_drone % len(self.drones)]
            await drone.goto(poi[0], poi[1], 80)
            print(f"🔄 Drone {current_drone} on station")
            await asyncio.sleep(3600)  # 1 hour per drone
            current_drone += 1
            # In real: land previous, takeoff next
