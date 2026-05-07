"""Replay a flight log against the event bus.

Loads a CSV (Airdata or DatCon format) and re-publishes it as live telemetry
on an EventBus. Useful for testing dashboards and analytics pipelines
against real flight data without flying.
"""
from __future__ import annotations

import asyncio
import csv
import logging
from pathlib import Path
from typing import Optional

from skycore.core.event_bus import EventBus

log = logging.getLogger(__name__)


_TIME_COLS = ["time(millisecond)", "time(ms)", "time"]
_LAT = ["latitude"]
_LON = ["longitude"]
_ALT = ["height_above_takeoff(meters)", "height_above_takeoff(feet)", "altitude(meters)"]
_BATT = ["battery_percent"]
_VOLT = ["voltage(v)"]
_YAW = ["compass_heading(degrees)", "yaw(degrees)"]
_GPS = ["gps_satellites", "satellites"]


def _first(row: dict, candidates: list[str]) -> Optional[str]:
    for c in candidates:
        if c in row:
            return c
    return None


async def replay_csv(path: Path | str, bus: EventBus, speedup: float = 1.0, topic: str = "telemetry") -> None:
    """Stream a CSV through the bus.

    speedup: 1.0 = real time, 10.0 = ten times faster, etc.
    """
    p = Path(path)
    rows: list[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    if not rows:
        return
    sample = rows[0]
    time_col = _first(sample, _TIME_COLS)
    lat_col = _first(sample, _LAT)
    lon_col = _first(sample, _LON)
    alt_col = _first(sample, _ALT)
    batt_col = _first(sample, _BATT)
    volt_col = _first(sample, _VOLT)
    yaw_col = _first(sample, _YAW)
    gps_col = _first(sample, _GPS)
    alt_to_m = 0.3048 if alt_col and "feet" in alt_col else 1.0

    last_t: Optional[float] = None
    for row in rows:
        try:
            t_ms = float(row[time_col]) if time_col else 0.0
        except (TypeError, ValueError, KeyError):
            t_ms = 0.0
        if last_t is not None and t_ms > last_t:
            wait = (t_ms - last_t) / 1000.0 / max(speedup, 0.001)
            if wait > 0:
                await asyncio.sleep(min(wait, 1.0))
        last_t = t_ms

        msg = {
            "timestamp": str(t_ms),
            "position": {
                "lat": float(row.get(lat_col, 0) or 0) if lat_col else 0,
                "lon": float(row.get(lon_col, 0) or 0) if lon_col else 0,
                "alt": float(row.get(alt_col, 0) or 0) * alt_to_m if alt_col else 0,
            },
            "battery": {
                "percent": float(row.get(batt_col, 0) or 0) if batt_col else 0,
                "voltage": float(row.get(volt_col, 0) or 0) if volt_col else 0,
            },
            "yaw": float(row.get(yaw_col, 0) or 0) if yaw_col else 0,
            "pitch": 0,
            "roll": 0,
            "velocity": {"forward": 0, "right": 0, "down": 0},
            "gimbal": {"pitch": 0},
            "mode": "replay",
            "home": None,
            "motors": [0, 0, 0, 0],
            "gps": {"satellites": int(float(row.get(gps_col, 0) or 0))} if gps_col else {"satellites": 0},
            "signal": 100,
        }
        await bus.publish(topic, msg)
