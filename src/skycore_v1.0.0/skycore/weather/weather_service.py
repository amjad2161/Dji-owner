"""Weather service for drone operations."""

import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import time

import logging

logger = logging.getLogger(__name__)


class WeatherCondition(Enum):
    """Weather condition classification."""
    GOOD = "good"
    MARGINAL = "marginal"
    POOR = "poor"
    DANGEROUS = "dangerous"


@dataclass
class WeatherForecast:
    """Weather forecast for planning."""
    timestamp: float
    wind_speed_kph: float
    wind_gust_kph: float
    precipitation_mm_h: float
    cloud_cover_pct: float
    temperature_c: float
    visibility_km: float = 10.0


class WeatherService:
    """
    Weather service for flight planning and safety.
    
    Features:
    - Real-time weather from Open-Meteo API
    - Forecast integration
    - Safety checks
    - Alert generation
    """
    
    def __init__(self):
        self.current_weather = None
        self.forecast: List[WeatherForecast] = []
        self.max_wind_kph = 36.0
        self.max_gust_kph = 50.0
        self._update_interval = 300  # 5 minutes
        self._last_update = 0.0
        self._running = False
    
    async def initialize(self):
        """Initialize weather service."""
        logger.info("Weather service initialized")
        self._running = True
    
    async def update_weather(self, lat: float, lon: float) -> bool:
        """Update current weather from API."""
        try:
            from skycore.openmeteo import current_weather, WeatherSnapshot
            
            snap = current_weather(lat, lon, timeout_s=10.0)
            self.current_weather = snap
            self._last_update = time.time()
            
            logger.info(f"Weather updated: {snap.wind_speed_kph:.0f} kph, {snap.temperature_c:.1f}C")
            return True
            
        except Exception as e:
            logger.error(f"Weather update failed: {e}")
            return False
    
    async def get_weather(self, lat: float, lon: float) -> Optional['WeatherSnapshot']:
        """Get current weather, updating if needed."""
        if self.current_weather is None or (time.time() - self._last_update) > self._update_interval:
            await self.update_weather(lat, lon)
        return self.current_weather
    
    def get_condition(self) -> WeatherCondition:
        """Get current weather condition classification."""
        if self.current_weather is None:
            return WeatherCondition.UNKNOWN
        
        wind = self.current_weather.wind_speed_kph
        gusts = self.current_weather.wind_gust_kph
        precip = self.current_weather.precipitation_mm_h
        clouds = self.current_weather.cloud_cover_pct
        
        if wind > 40 or gusts > 60 or precip > 5:
            return WeatherCondition.DANGEROUS
        elif wind > 25 or gusts > 40 or precip > 1:
            return WeatherCondition.POOR
        elif wind > 15 or clouds > 80:
            return WeatherCondition.MARGINAL
        else:
            return WeatherCondition.GOOD
    
    def is_safe_for_flight(self) -> Tuple[bool, List[str]]:
        """Check if current conditions are safe for flight."""
        issues = []
        
        if self.current_weather is None:
            return False, ["No weather data"]
        
        if self.current_weather.wind_speed_kph > self.max_wind_kph:
            issues.append(f"Wind speed {self.current_weather.wind_speed_kph:.0f} kph exceeds {self.max_wind_kph:.0f} kph")
        
        if self.current_weather.wind_gust_kph > self.max_gust_kph:
            issues.append(f"Wind gusts {self.current_weather.wind_gust_kph:.0f} kph exceeds {self.max_gust_kph:.0f} kph")
        
        if self.current_weather.precipitation_mm_h > 0.5:
            issues.append(f"Precipitation {self.current_weather.precipitation_mm_h:.1f} mm/h")
        
        if self.current_weather.temperature_c < -5 or self.current_weather.temperature_c > 40:
            issues.append(f"Temperature {self.current_weather.temperature_c:.1f}C out of range")
        
        return len(issues) == 0, issues
    
    def get_statistics(self) -> Dict:
        """Get weather service statistics."""
        return {
            'has_current_weather': self.current_weather is not None,
            'wind_speed_kph': self.current_weather.wind_speed_kph if self.current_weather else 0,
            'temperature_c': self.current_weather.temperature_c if self.current_weather else 0,
            'condition': self.get_condition().value if self.current_weather else 'unknown',
            'last_update': self._last_update
        }


# Re-export from openmeteo for convenience
from skycore.openmeteo import WeatherSnapshot, current_weather, preflight_check

# Re-export from wind_model for convenience
from skycore.weather.wind_model import WindData, WindEffect

__all__ = ['WeatherService', 'WeatherCondition', 'WeatherForecast', 
           'WeatherSnapshot', 'current_weather', 'preflight_check',
           'WindData', 'WindEffect']