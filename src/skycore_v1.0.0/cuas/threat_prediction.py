"""
SkyCore C-UAS Threat Prediction Module
AI-powered prediction of drone threat behavior based on trajectory analysis
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ThreatTrajectory:
    """Track history of a threat's movement."""
    drone_id: str
    positions: list[tuple[float, float, float]]  # (lat, lon, alt)
    velocities: list[tuple[float, float, float]]  # (vx, vy, vz) m/s
    timestamps: list[float]  # Unix timestamps
    threat_type: Optional[str] = None

    def add_point(self, lat: float, lon: float, alt: float) -> None:
        now = time.time()
        self.positions.append((lat, lon, alt))
        self.timestamps.append(now)

        # Calculate velocity if we have previous point
        if len(self.positions) >= 2:
            dt = now - self.timestamps[-2]
            if dt > 0:
                vx = (lon - self.positions[-2][1]) * 111320 * math.cos(math.radians(lat)) / dt
                vy = (lat - self.positions[-2][0]) * 111320 / dt
                vz = (alt - self.positions[-2][2]) / dt
                self.velocities.append((vx, vy, vz))

    @property
    def avg_speed_ms(self) -> float:
        if len(self.velocities) < 2:
            return 0
        speeds = [math.sqrt(vx**2 + vy**2) for vx, vy, vz in self.velocities]
        return sum(speeds) / len(speeds)

    @property
    def heading_deg(self) -> float:
        if len(self.velocities) < 1:
            return 0
        vx, vy, _ = self.velocities[-1]
        return math.degrees(math.atan2(vx, vy)) % 360


@dataclass
class PredictedThreat:
    """Predicted future threat state."""
    drone_id: str
    predicted_position: tuple[float, float, float]  # lat, lon, alt
    predicted_time_s: float  # seconds from now
    time_to_intercept_s: float  # if intercepting our position
    intent: str  # "Surveillance", "Patrol", "Approaching", "Unknown"
    confidence: float  # 0-1
    threat_level: str  # LOW, MEDIUM, HIGH, CRITICAL

    def to_dict(self) -> dict:
        return {
            "drone_id": self.drone_id,
            "predicted_lat": self.predicted_position[0],
            "predicted_lon": self.predicted_position[1],
            "predicted_alt_m": self.predicted_position[2],
            "predicted_time_s": self.predicted_time_s,
            "time_to_intercept_s": self.time_to_intercept_s,
            "intent": self.intent,
            "confidence": self.confidence,
            "threat_level": self.threat_level,
        }


class ThreatPredictor:
    """AI-powered threat trajectory prediction.

    Uses multiple models:
    1. Linear extrapolation (baseline)
    2. Velocity-based prediction (interception time)
    3. Behavior classification (intent analysis)
    """

    def __init__(
        self,
        history_window_s: float = 60.0,
        prediction_horizon_s: float = 30.0,
    ):
        self.history_window_s = history_window_s
        self.prediction_horizon_s = prediction_horizon_s
        self._trajectories: dict[str, ThreatTrajectory] = {}
        self._lock = asyncio.Lock()

    def track(self, drone_id: str, lat: float, lon: float, alt: float) -> None:
        """Update trajectory for a drone."""
        if drone_id not in self._trajectories:
            self._trajectories[drone_id] = ThreatTrajectory(
                drone_id=drone_id,
                positions=[],
                velocities=[],
                timestamps=[],
            )

        traj = self._trajectories[drone_id]
        traj.add_point(lat, lon, alt)

        # Prune old points
        now = time.time()
        cutoff = now - self.history_window_s
        while traj.timestamps and traj.timestamps[0] < cutoff:
            traj.positions.pop(0)
            traj.timestamps.pop(0)
            if traj.velocities:
                traj.velocities.pop(0)

    def predict_intercept_time(
        self,
        drone_lat: float,
        drone_lon: float,
        drone_alt: float,
        target_lat: float,
        target_lon: float,
        target_alt: float,
        current_speed_ms: float,
    ) -> float:
        """Calculate time for drone to reach target position."""
        dist_m = self._haversine_m(drone_lat, drone_lon, target_lat, target_lon)
        alt_diff_m = abs(drone_alt - target_alt)

        # Combined 3D distance
        distance_3d = math.sqrt(dist_m**2 + alt_diff_m**2)

        if current_speed_ms < 1:
            return float('inf')

        return distance_3d / current_speed_ms

    def predict_threat(
        self,
        drone_id: str,
        our_lat: float,
        our_lon: float,
        our_alt: float,
        prediction_time_s: float = 10.0,
    ) -> Optional[PredictedThreat]:
        """Predict where a threat will be and if it will intercept us."""
        if drone_id not in self._trajectories:
            return None

        traj = self._trajectories[drone_id]
        if len(traj.positions) < 3:
            return None

        # Calculate average velocity vector
        vx, vy, vz = self._average_velocity(traj)

        # Predict future position
        last_lat, last_lon, last_alt = traj.positions[-1]
        future_lat = last_lat + (vy * prediction_time_s) / 111320
        future_lon = last_lon + (vx * prediction_time_s) / (
            111320 * max(0.01, math.cos(math.radians(last_lat)))
        )
        future_alt = last_alt + vz * prediction_time_s

        # Clamp altitude
        future_alt = max(0, min(future_alt, 400))

        # Calculate intercept time
        intercept_time = self.predict_intercept_time(
            future_lat, future_lon, future_alt,
            our_lat, our_lon, our_alt,
            traj.avg_speed_ms,
        )

        # Determine intent based on behavior
        intent = self._classify_intent(traj, intercept_time)

        # Threat level based on intercept time
        if intercept_time < 30:
            level = "CRITICAL"
            confidence = 0.95
        elif intercept_time < 60:
            level = "HIGH"
            confidence = 0.85
        elif intercept_time < 120:
            level = "MEDIUM"
            confidence = 0.70
        else:
            level = "LOW"
            confidence = 0.60

        # Boost confidence if we have more historical data
        confidence = min(0.99, confidence + len(traj.positions) * 0.01)

        return PredictedThreat(
            drone_id=drone_id,
            predicted_position=(future_lat, future_lon, future_alt),
            predicted_time_s=prediction_time_s,
            time_to_intercept_s=intercept_time,
            intent=intent,
            confidence=confidence,
            threat_level=level,
        )

    def predict_all(
        self,
        our_lat: float,
        our_lon: float,
        our_alt: float,
        prediction_time_s: float = 10.0,
    ) -> list[PredictedThreat]:
        """Predict threats for all tracked drones."""
        predictions = []
        for drone_id in self._trajectories:
            pred = self.predict_threat(drone_id, our_lat, our_lon, our_alt, prediction_time_s)
            if pred:
                predictions.append(pred)

        # Sort by threat level and intercept time
        predictions.sort(key=lambda p: (
            {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}[p.threat_level],
            p.time_to_intercept_s,
        ))
        return predictions

    def _average_velocity(self, traj: ThreatTrajectory) -> tuple[float, float, float]:
        """Calculate average velocity from trajectory."""
        if not traj.velocities:
            return (0, 0, 0)

        vx_sum = sum(v[0] for v in traj.velocities[-5:])  # Last 5 points
        vy_sum = sum(v[1] for v in traj.velocities[-5:])
        vz_sum = sum(v[2] for v in traj.velocities[-5:])
        n = len(traj.velocities[-5:])

        return (vx_sum / n, vy_sum / n, vz_sum / n)

    def _classify_intent(self, traj: ThreatTrajectory, intercept_time_s: float) -> str:
        """Classify threat intent based on behavior."""
        if len(traj.positions) < 5:
            return "Unknown"

        # Check for circling/loitering behavior
        positions = traj.positions[-10:]
        if len(positions) >= 10:
            center_lat = sum(p[0] for p in positions) / len(positions)
            center_lon = sum(p[1] for p in positions) / len(positions)

            # Calculate variance from center
            variance = sum(
                (p[0] - center_lat)**2 + (p[1] - center_lon)**2
                for p in positions
            ) / len(positions)

            # Low variance = circling behavior
            if variance < 0.00001:  # ~100m radius
                return "Patrol"

        # Check for approach behavior
        if intercept_time_s < 60:
            return "Approaching"

        # Check for hover/surveillance
        if traj.avg_speed_ms < 3:
            return "Surveillance"

        return "Transit"

    def _haversine_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance in meters."""
        R = 6371000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon/2)**2)
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def get_trajectory(self, drone_id: str) -> Optional[ThreatTrajectory]:
        return self._trajectories.get(drone_id)


# Global predictor
default_predictor = ThreatPredictor()