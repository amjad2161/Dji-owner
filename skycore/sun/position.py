"""Sun azimuth + elevation calculator for cinematography planning.

Useful for:
- "What time is the sun behind me when I shoot from this point at this bearing?"
- "When does light hit this east-facing facade?"
- "What's the angle of incidence for ground photogrammetry coverage?"

Uses `astral` for sun ephemeris.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass
class SunPosition:
    azimuth_deg: float    # 0° = N, 90° = E
    elevation_deg: float  # 0° = horizon, 90° = zenith

    @property
    def is_above_horizon(self) -> bool:
        return self.elevation_deg > 0


def sun_position(lat: float, lon: float, when: Optional[datetime] = None) -> SunPosition:
    try:
        from astral import Observer
        from astral.sun import azimuth, elevation
    except ImportError as e:
        raise ImportError("astral is required. pip install astral") from e
    when = when or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    observer = Observer(latitude=lat, longitude=lon)
    return SunPosition(
        azimuth_deg=azimuth(observer, when),
        elevation_deg=elevation(observer, when),
    )


def golden_hours_today(lat: float, lon: float, date: Optional[datetime] = None) -> dict:
    try:
        from astral import Observer
        from astral.sun import sun
    except ImportError as e:
        raise ImportError("astral is required. pip install astral") from e
    date = date or datetime.now(timezone.utc)
    o = Observer(latitude=lat, longitude=lon)
    s = sun(o, date=date.date(), tzinfo=timezone.utc)
    return {
        "sunrise": s["sunrise"].isoformat(),
        "morning_golden_end": (s["sunrise"] + timedelta(hours=1)).isoformat(),
        "noon": s["noon"].isoformat(),
        "evening_golden_start": (s["sunset"] - timedelta(hours=1)).isoformat(),
        "sunset": s["sunset"].isoformat(),
    }


def best_time_for_bearing(
    lat: float,
    lon: float,
    desired_sun_bearing_deg: float,
    date: Optional[datetime] = None,
    tolerance_deg: float = 10.0,
) -> Optional[datetime]:
    """Find the time of day when the sun azimuth is within tolerance of desired_sun_bearing_deg.

    Useful when you want the sun behind the camera (camera_bearing + 180) for warm side-light shots.
    """
    date = date or datetime.now(timezone.utc)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    base = date.replace(hour=0, minute=0, second=0, microsecond=0)
    best = None
    best_err = 360.0
    for minute in range(0, 24 * 60, 5):
        t = base + timedelta(minutes=minute)
        pos = sun_position(lat, lon, t)
        if not pos.is_above_horizon:
            continue
        err = abs((pos.azimuth_deg - desired_sun_bearing_deg + 540) % 360 - 180)
        if err < best_err:
            best_err = err
            best = t
    return best if best is not None and best_err <= tolerance_deg else best
