"""
SkyCore ADS-B Awareness
Real-time manned aircraft detection via OpenSky Network + dump1090
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple

@dataclass
class Aircraft:
    icao: str
    callsign: str
    lat: float
    lon: float
    alt: float
    distance_m: float
    threat_level: str  # LOW / MEDIUM / HIGH

class ADSBMonitor:
    def __init__(self):
        self.aircraft: List[Aircraft] = []

    async def poll_opensky(self, drone_lat: float, drone_lon: float, radius_km: float = 10.0):
        # Real implementation would call https://opensky-network.org/api/states/all
        # Mock for demo
        self.aircraft = [
            Aircraft("4B1234", "BAW123", 32.09, 34.78, 850, 1200, "MEDIUM"),
            Aircraft("AABBCC", "UAL456", 32.07, 34.76, 1200, 4500, "LOW")
        ]
        print(f"✈️ ADS-B: {len(self.aircraft)} aircraft detected nearby")

    def get_threats(self, drone_pos: Tuple[float, float, float]) -> List[Aircraft]:
        threats = []
        for ac in self.aircraft:
            dist = ((ac.lat - drone_pos[0])**2 + (ac.lon - drone_pos[1])**2)**0.5 * 111320
            if dist < 3000 and abs(ac.alt - drone_pos[2]) < 300:
                ac.distance_m = dist
                ac.threat_level = "HIGH" if dist < 1500 else "MEDIUM"
                threats.append(ac)
        return threats

    async def run_monitor(self, drone_pos: Tuple[float, float, float]):
        while True:
            await self.poll_opensky(drone_pos[0], drone_pos[1])
            threats = self.get_threats(drone_pos)
            for t in threats:
                print(f"🚨 THREAT: {t.callsign} at {t.distance_m:.0f}m, alt {t.alt}m")
            await asyncio.sleep(10)
