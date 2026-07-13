"""
SkyCore Weather - Pre-flight weather check (Open-Meteo)
"""

import asyncio
from dataclasses import dataclass

@dataclass
class WeatherReport:
    wind_speed: float
    wind_gust: float
    visibility: float
    precipitation: float
    safe_to_fly: bool

class WeatherService:
    async def get_forecast(self, lat: float, lon: float) -> WeatherReport:
        # In production: real API call to open-meteo.com
        # For now: safe mock
        return WeatherReport(
            wind_speed=4.2,
            wind_gust=6.8,
            visibility=10.0,
            precipitation=0.0,
            safe_to_fly=True
        )

    def is_safe(self, report: WeatherReport, max_wind: float = 10.0) -> bool:
        return (report.wind_speed < max_wind and 
                report.visibility > 3.0 and 
                report.precipitation < 0.5)
