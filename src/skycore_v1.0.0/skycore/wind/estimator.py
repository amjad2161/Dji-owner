"""
SkyCore Wind Estimator
Estimates wind speed/direction from telemetry (legal, no hardware mods)
"""

from dataclasses import dataclass
from typing import List

@dataclass
class WindEstimate:
    speed_ms: float
    direction_deg: float
    confidence: float

class WindEstimator:
    def estimate_from_telemetry(self, telemetry_history: List[dict]) -> WindEstimate:
        if len(telemetry_history) < 5:
            return WindEstimate(0, 0, 0.1)
        
        # Simple estimation from ground speed vs airspeed difference (placeholder)
        speeds = [t.get('ground_speed', 0) for t in telemetry_history[-10:]]
        avg_speed = sum(speeds) / len(speeds)
        
        # In real: use IMU + GPS drift analysis
        wind_speed = max(0, avg_speed - 8)  # assume airspeed ~8 m/s
        direction = 180  # placeholder
        
        return WindEstimate(
            speed_ms=round(wind_speed, 1),
            direction_deg=direction,
            confidence=0.75
        )
