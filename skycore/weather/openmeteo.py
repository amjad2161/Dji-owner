"""Pre-flight weather check using Open-Meteo (free, no API key).

https://open-meteo.com provides current and forecast weather without any
authentication. We pull the conditions relevant to drone flight and assess
against common safety thresholds.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass

log = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Manufacturer wind tolerances (advisory):
#   Mavic 3 family: 12 m/s = 43 kph
#   Air 2S / Air 3:  10.7 m/s = 38 kph
#   Mini 4 Pro:       10.7 m/s = 38 kph
#   Mini 3 / 2:       8.5 m/s = 30 kph
DEFAULT_MAX_WIND_KPH = 36.0
DEFAULT_MAX_GUST_KPH = 50.0


@dataclass
class WeatherSnapshot:
    temperature_c: float
    wind_speed_kph: float
    wind_gust_kph: float
    wind_direction_deg: float
    precipitation_mm_h: float
    cloud_cover_pct: float
    pressure_hpa: float
    humidity_pct: float

    def is_safe_for_drone(
        self,
        max_wind_kph: float = DEFAULT_MAX_WIND_KPH,
        max_gust_kph: float = DEFAULT_MAX_GUST_KPH,
        max_precip_mm_h: float = 0.1,
        min_temp_c: float = -10.0,
        max_temp_c: float = 40.0,
    ) -> tuple[bool, list[str]]:
        issues: list[str] = []
        if self.wind_speed_kph > max_wind_kph:
            issues.append(f"Wind {self.wind_speed_kph:.1f} kph > {max_wind_kph:.0f} kph")
        if self.wind_gust_kph > max_gust_kph:
            issues.append(f"Gust {self.wind_gust_kph:.1f} kph > {max_gust_kph:.0f} kph")
        if self.precipitation_mm_h > max_precip_mm_h:
            issues.append(f"Precipitation {self.precipitation_mm_h:.1f} mm/h")
        if self.temperature_c < min_temp_c:
            issues.append(f"Temperature {self.temperature_c:.1f}°C below {min_temp_c}°C")
        if self.temperature_c > max_temp_c:
            issues.append(f"Temperature {self.temperature_c:.1f}°C above {max_temp_c}°C")
        return (not issues), issues


def current_weather(lat: float, lon: float, timeout_s: float = 10.0) -> WeatherSnapshot:
    """Fetch the current weather snapshot at lat/lon."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,relative_humidity_2m,precipitation,cloud_cover,"
            "surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m"
        ),
        "wind_speed_unit": "kmh",
    }
    url = f"{OPEN_METEO_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    cur = data.get("current", {})
    return WeatherSnapshot(
        temperature_c=float(cur.get("temperature_2m", 0)),
        wind_speed_kph=float(cur.get("wind_speed_10m", 0)),
        wind_gust_kph=float(cur.get("wind_gusts_10m", 0)),
        wind_direction_deg=float(cur.get("wind_direction_10m", 0)),
        precipitation_mm_h=float(cur.get("precipitation", 0)),
        cloud_cover_pct=float(cur.get("cloud_cover", 0)),
        pressure_hpa=float(cur.get("surface_pressure", 1013)),
        humidity_pct=float(cur.get("relative_humidity_2m", 0)),
    )


def preflight_check(
    lat: float,
    lon: float,
    max_wind_kph: float = DEFAULT_MAX_WIND_KPH,
    max_gust_kph: float = DEFAULT_MAX_GUST_KPH,
) -> tuple[bool, list[str], WeatherSnapshot]:
    """Convenience: fetch weather and return (ok, issues, snapshot)."""
    snap = current_weather(lat, lon)
    ok, issues = snap.is_safe_for_drone(max_wind_kph=max_wind_kph, max_gust_kph=max_gust_kph)
    return ok, issues, snap
