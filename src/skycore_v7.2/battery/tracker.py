"""
SkyCore Battery Health Tracker
Cycle counting, health estimation, RTH recommendations
"""

from dataclasses import dataclass
from datetime import datetime

@dataclass
class BatteryHealth:
    serial: str
    cycle_count: int
    health_percent: float
    last_charge: datetime
    estimated_flights_left: int

class BatteryTracker:
    def __init__(self):
        self.batteries = {}

    def register(self, serial: str, initial_health: float = 100.0):
        self.batteries[serial] = BatteryHealth(
            serial=serial,
            cycle_count=0,
            health_percent=initial_health,
            last_charge=datetime.now(),
            estimated_flights_left=45
        )

    def log_flight(self, serial: str, flight_minutes: float):
        if serial in self.batteries:
            b = self.batteries[serial]
            b.cycle_count += 1
            b.health_percent = max(70, b.health_percent - (flight_minutes / 200))
            b.estimated_flights_left = int((b.health_percent - 70) * 1.5)
            print(f"🔋 {serial}: Health {b.health_percent:.1f}% | Flights left: {b.estimated_flights_left}")
