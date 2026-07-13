"""
SkyCore Wind Model
=================
Wind estimation and forecasting for flight planning.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

log = logging.getLogger(__name__)


@dataclass
class WindEstimate:
    """Wind estimate at altitude."""
    speed_ms: float
    direction_deg: float  # Direction wind is going to
    gust_speed_ms: float = 0.0
    turbulence: float = 0.0
    timestamp: float = 0.0
    
    @property
    def heading(self) -> float:
        """Wind heading (direction it's going to)."""
        return self.direction_deg
    
    @property
    def tailwind_component(self, heading: float) -> float:
        """Tailwind component for given heading."""
        return self.speed_ms * np.cos(np.radians(self.direction_deg - heading))


class WindModel:
    """
    Wind estimation and prediction model.
    
    Features:
    - Real-time wind estimation from flight data
    - Wind forecast integration
    - Gust detection
    - Turbulence assessment
    """
    
    def __init__(self):
        self.current_wind = WindEstimate(speed_ms=0.0, direction_deg=0.0)
        self.forecasts: List[Dict] = []
        log.info("Wind Model initialized")
    
    def estimate_from_flight_data(self, velocity: Tuple[float, float, float],
                                 airspeed: float, heading: float) -> WindEstimate:
        """
        Estimate wind from flight data.
        
        Args:
            velocity: Ground velocity (vx, vy, vz) in m/s
            airspeed: Airspeed in m/s
            heading: Aircraft heading in degrees
            
        Returns:
            WindEstimate
        """
        vx, vy, _ = velocity
        
        # Ground track
        ground_track = np.degrees(np.arctan2(vy, vx))
        
        # Wind triangle
        wind_speed = 0.0  # Placeholder
        wind_dir = ground_track  # Placeholder
        
        return WindEstimate(
            speed_ms=wind_speed,
            direction_deg=wind_dir,
            timestamp=0.0
        )
    
    def get_wind_at_altitude(self, alt: float) -> WindEstimate:
        """Get wind estimate at specific altitude."""
        # Power law extrapolation
        ref_alt = 10.0  # meters
        alpha = 0.15  # Surface roughness coefficient
        
        ratio = (alt / ref_alt) ** alpha
        speed = self.current_wind.speed_ms * ratio
        
        return WindEstimate(
            speed_ms=speed,
            direction_deg=self.current_wind.direction_deg
        )
    
    def get_gust_factor(self, alt: float) -> float:
        """Get gust factor at altitude."""
        base_gust = 1.5  # m/s
        return base_gust * (alt / 50) ** 0.5
    
    def is_safe_to_fly(self, max_wind: float = 40.0) -> Tuple[bool, str]:
        """Check if conditions are safe for flight."""
        if self.current_wind.speed_ms > max_wind:
            return False, f"Wind too strong: {self.current_wind.speed_ms:.1f} m/s"
        return True, "Conditions safe"


__all__ = ['WindModel', 'WindEstimate']