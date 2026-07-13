"""Wind model for flight dynamics compensation."""

import math
import asyncio
from typing import Tuple, Dict, Optional, List
from dataclasses import dataclass
from enum import Enum

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class WindDirection(Enum):
    """Wind direction compass."""
    N = 0
    NE = 45
    E = 90
    SE = 135
    S = 180
    SW = 225
    W = 270
    NW = 315


@dataclass
class WindData:
    """Wind measurement data."""
    speed_mps: float  # meters per second
    direction_deg: float  # degrees (0 = North, 90 = East)
    gust_mps: float = 0.0  # gust speed
    timestamp: float = 0.0


@dataclass
class WindEffect:
    """Calculated wind effect on drone."""
    vx_compensation: float  # compensation in forward axis
    vy_compensation: float  # compensation in right axis
    vz_compensation: float  # compensation in down axis
    magnitude: float


class WindModel(LoggerMixin):
    """
    Wind effect model for drone flight dynamics.
    
    Features:
    - Wind estimation from telemetry
    - Compensation for gusts
    - Altitude-dependent wind modeling
    - Wind forecasting integration
    """
    
    def __init__(self, drag_coefficient: float = 0.5):
        self.drag_coefficient = drag_coefficient
        self.wind_history: List[WindData] = []
        self.max_history = 100
        
        # Wind model parameters
        self.base_wind = (0.0, 0.0)  # (vx, vy) m/s
        self.wind_gust_max = 5.0  # max gust m/s
        self.altitude_scale_height = 100.0  # meters
        
        self._initialized = True
        logger.info("Wind model initialized")
    
    def estimate_wind_from_telemetry(self, velocity_ned: Tuple[float, float, float],
                                     commanded_velocity: Tuple[float, float, float],
                                     attitude: Tuple[float, float, float]) -> WindData:
        """
        Estimate wind from difference between commanded and actual velocity.
        
        Args:
            velocity_ned: Actual velocity in NED frame (m/s)
            commanded_velocity: Commanded velocity (m/s)
            attitude: Drone attitude (roll, pitch, yaw) in radians
        
        Returns:
            WindData with estimated wind
        """
        # Simple wind estimation: difference between actual and commanded
        # This is a simplification - real implementation would use Kalman filter
        vx_actual, vy_actual, vz_actual = velocity_ned
        vx_cmd, vy_cmd, vz_cmd = commanded_velocity
        
        # Wind affects horizontal velocity
        wind_vx = (vx_actual - vx_cmd) * 0.5
        wind_vy = (vy_actual - vy_cmd) * 0.5
        
        wind_speed = math.sqrt(wind_vx**2 + wind_vy**2)
        wind_dir = math.degrees(math.atan2(wind_vy, wind_vx)) % 360
        
        # Detect gusts from vertical velocity
        gust = abs(vz_actual - vz_cmd) * 2
        
        wind = WindData(
            speed_mps=wind_speed,
            direction_deg=wind_dir,
            gust_mps=min(gust, self.wind_gust_max),
            timestamp=asyncio.get_event_loop().time()
        )
        
        self._add_wind_measurement(wind)
        return wind
    
    def _add_wind_measurement(self, wind: WindData):
        """Add wind measurement to history."""
        self.wind_history.append(wind)
        if len(self.wind_history) > self.max_history:
            self.wind_history.pop(0)
    
    def calculate_compensation(self, wind: WindData, altitude_m: float,
                               drone_velocity: Tuple[float, float, float]) -> WindEffect:
        """
        Calculate velocity compensation needed to counter wind.
        
        Args:
            wind: Current wind data
            altitude_m: Drone altitude
            drone_velocity: Current drone velocity (m/s)
        
        Returns:
            WindEffect with compensation values
        """
        # Altitude-dependent wind model (wind increases with altitude)
        alt_factor = 1.0 + (altitude_m / self.altitude_scale_height) * 0.3
        effective_wind_speed = wind.speed_mps * alt_factor
        
        # Wind direction to vector
        wind_rad = math.radians(wind.direction_deg)
        wind_vx = effective_wind_speed * math.sin(wind_rad)  # N component
        wind_vy = effective_wind_speed * math.cos(wind_rad)  # E component
        
        # Add gust component
        if wind.gust_mps > 0:
            # Gusts add random vertical component
            wind_vx += wind.gust_mps * 0.3 * math.sin(wind_rad)
            wind_vy += wind.gust_mps * 0.3 * math.cos(wind_rad)
        
        # Compensation is opposite to wind direction
        # Scale by drag coefficient
        compensation_scale = self.drag_coefficient * 0.5
        vx_comp = -wind_vx * compensation_scale
        vy_comp = -wind_vy * compensation_scale
        vz_comp = -wind.gust_mps * 0.2 if wind.gust_mps > 0 else 0.0
        
        # Add current velocity as damping
        vx_comp += drone_velocity[0] * 0.1
        vy_comp += drone_velocity[1] * 0.1
        
        magnitude = math.sqrt(vx_comp**2 + vy_comp**2 + vz_comp**2)
        
        return WindEffect(
            vx_compensation=vx_comp,
            vy_compensation=vy_comp,
            vz_compensation=vz_comp,
            magnitude=magnitude
        )
    
    def get_average_wind(self, seconds: float = 60.0) -> Optional[WindData]:
        """Get average wind over time period."""
        if not self.wind_history:
            return None
        
        current_time = self.wind_history[-1].timestamp if self.wind_history else 0
        recent = [w for w in self.wind_history if current_time - w.timestamp <= seconds]
        
        if not recent:
            return None
        
        avg_speed = sum(w.speed_mps for w in recent) / len(recent)
        avg_dir = sum(math.sin(math.radians(w.direction_deg)) for w in recent) / len(recent)
        avg_dir_y = sum(math.cos(math.radians(w.direction_deg)) for w in recent) / len(recent)
        avg_gust = sum(w.gust_mps for w in recent) / len(recent)
        
        avg_dir_deg = math.degrees(math.atan2(avg_dir, avg_dir_y)) % 360
        
        return WindData(
            speed_mps=avg_speed,
            direction_deg=avg_dir_deg,
            gust_mps=avg_gust
        )
    
    def predict_wind(self, altitude_m: float) -> WindData:
        """Predict wind at given altitude."""
        avg = self.get_average_wind(300)  # 5 minute average
        
        if avg:
            # Wind increases with altitude
            alt_factor = 1.0 + (altitude_m / self.altitude_scale_height) * 0.2
            return WindData(
                speed_mps=avg.speed_mps * alt_factor,
                direction_deg=avg.direction_deg,
                gust_mps=avg.gust_mps * 0.5
            )
        
        return WindData(speed_mps=0, direction_deg=0, gust_mps=0)
    
    def get_wind_safe_limit(self) -> float:
        """Get safe wind speed limit for operations."""
        avg = self.get_average_wind(60)
        if avg and avg.speed_mps > 10:
            return 8.0  # Reduce limit in high wind
        return 12.0  # Normal limit m/s
    
    def get_statistics(self) -> Dict:
        """Get wind model statistics."""
        avg = self.get_average_wind(60)
        return {
            'avg_wind_mps': avg.speed_mps if avg else 0,
            'avg_direction_deg': avg.direction_deg if avg else 0,
            'max_gust_mps': max((w.gust_mps for w in self.wind_history), default=0),
            'measurement_count': len(self.wind_history),
            'safe_limit_mps': self.get_wind_safe_limit()
        }