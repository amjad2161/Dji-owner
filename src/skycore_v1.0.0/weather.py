"""Weather module - re-exports from openmeteo for backward compatibility.

The main implementation lives in `openmeteo.py`. This module provides
a unified import point and any additional weather utilities.
"""
from __future__ import annotations

from skycore.openmeteo import (
    WeatherSnapshot,
    current_weather,
    preflight_check,
    DEFAULT_MAX_WIND_KPH,
    DEFAULT_MAX_GUST_KPH,
)

__all__ = [
    "WeatherSnapshot",
    "current_weather",
    "preflight_check",
    "DEFAULT_MAX_WIND_KPH",
    "DEFAULT_MAX_GUST_KPH",
]


def weather_score(snap: WeatherSnapshot) -> float:
    """Compute a 0-100 flight-weather score based on conditions.

    Factors:
    - Wind (heaviest weight)
    - Precipitation
    - Cloud cover
    - Temperature extremes
    """
    score = 100.0

    # Wind penalty (max 40 points)
    if snap.wind_speed_kph > 50:
        score -= 40
    elif snap.wind_speed_kph > 30:
        score -= 20
    elif snap.wind_speed_kph > 20:
        score -= 10

    # Gust penalty (max 20 points)
    if snap.wind_gust_kph > 60:
        score -= 20
    elif snap.wind_gust_kph > 40:
        score -= 10

    # Precipitation penalty (max 20 points)
    if snap.precipitation_mm_h > 5:
        score -= 20
    elif snap.precipitation_mm_h > 1:
        score -= 10

    # Cloud cover penalty (max 10 points)
    if snap.cloud_cover_pct > 90:
        score -= 10
    elif snap.cloud_cover_pct > 70:
        score -= 5

    # Temperature penalty (max 10 points)
    if snap.temperature_c < 0 or snap.temperature_c > 35:
        score -= 10
    elif snap.temperature_c < 5 or snap.temperature_c > 30:
        score -= 5

    return max(0.0, score)


def format_weather_report(snap: WeatherSnapshot) -> str:
    """Human-readable weather summary."""
    score = weather_score(snap)
    ok, issues = snap.is_safe_for_drone()

    lines = [
        f"🌤️  Weather Report",
        f"   Temperature: {snap.temperature_c:.1f}°C",
        f"   Wind: {snap.wind_speed_kph:.0f} kph @ {snap.wind_direction_deg:.0f}°",
        f"   Gusts: {snap.wind_gust_kph:.0f} kph",
        f"   Cloud cover: {snap.cloud_cover_pct:.0f}%",
        f"   Pressure: {snap.pressure_hpa:.0f} hPa",
        f"   Humidity: {snap.humidity_pct:.0f}%",
        "",
        f"📊 Flight Score: {score:.0f}/100",
    ]

    if ok:
        lines.append("✅ Conditions OK for flight")
    else:
        lines.append("⚠️  Issues:")
        for issue in issues:
            lines.append(f"   • {issue}")

    return "\n".join(lines)