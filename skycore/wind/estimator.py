"""Estimate wind from drone telemetry.

Method: compare commanded velocity (or attitude) to ground-track velocity.
Simple but useful: if the drone is hovering with non-zero pitch/roll, the
gimbal-stabilized aircraft is leaning into the wind. Pitch angle correlates
with airspeed which, combined with ground speed, gives a wind vector.

This is a coarse estimator suitable for advisory display. Industrial-grade
wind sensing requires a pitot-static system or onboard anemometer.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean
from typing import Iterable, Optional

from skycore.core.types import Telemetry


@dataclass
class WindEstimate:
    speed_mps: float
    bearing_deg: float  # the wind is BLOWING TOWARDS this bearing
    confidence: float  # 0–1

    @property
    def speed_kph(self) -> float:
        return self.speed_mps * 3.6


def estimate_wind(
    samples: Iterable[Telemetry],
    pitch_to_airspeed_factor: float = 0.5,  # m/s per degree of pitch
) -> Optional[WindEstimate]:
    """Estimate wind from a window of telemetry samples.

    Best results when the drone is hovering or flying at constant velocity.
    Returns None if not enough data.
    """
    samples = list(samples)
    if len(samples) < 5:
        return None

    east_speeds = []
    north_speeds = []
    for tm in samples:
        # Body-frame velocity: forward (vx), right (vy)
        vx, vy, _ = tm.velocity_xyz
        yaw_rad = math.radians(tm.yaw_deg)
        # Rotate body → world (NED): north = vx*cos(yaw) - vy*sin(yaw)
        north = vx * math.cos(yaw_rad) - vy * math.sin(yaw_rad)
        east = vx * math.sin(yaw_rad) + vy * math.cos(yaw_rad)

        # Airspeed from pitch (positive pitch = nose down = forward airspeed)
        airspeed_forward = tm.pitch_deg * pitch_to_airspeed_factor
        airspeed_right = tm.roll_deg * pitch_to_airspeed_factor
        air_north = airspeed_forward * math.cos(yaw_rad) - airspeed_right * math.sin(yaw_rad)
        air_east = airspeed_forward * math.sin(yaw_rad) + airspeed_right * math.cos(yaw_rad)

        # Wind = ground velocity - airspeed (in world frame)
        north_speeds.append(north - air_north)
        east_speeds.append(east - air_east)

    avg_n = mean(north_speeds)
    avg_e = mean(east_speeds)
    speed = math.hypot(avg_n, avg_e)
    bearing = (math.degrees(math.atan2(avg_e, avg_n)) + 360) % 360
    # Confidence: more samples + tighter variance → higher
    var = sum((n - avg_n) ** 2 + (e - avg_e) ** 2 for n, e in zip(north_speeds, east_speeds)) / len(samples)
    confidence = max(0.0, min(1.0, 1.0 - math.sqrt(var) / max(1.0, speed * 2)))
    return WindEstimate(speed_mps=speed, bearing_deg=bearing, confidence=confidence)
