"""Flight log analyzer (refactored from tools/log-analyzer/analyze.py).

Reads Airdata or DatCon CSV exports and returns a structured health
summary. Useful both as a CLI command and as a building block for the
web dashboard.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

COL_TIME = ["time(millisecond)", "time(ms)", "time", "OSD.flyTime [s]"]
COL_HEIGHT = [
    "height_above_takeoff(feet)",
    "height_above_takeoff(meters)",
    "OSD.height [m]",
    "altitude(feet)",
    "altitude(meters)",
]
COL_DIST = ["distance(feet)", "distance(meters)"]
COL_HSPEED = ["speed_horizontal(mph)", "speed_horizontal(kph)", "OSD.hSpeed [m/s]"]
COL_VSPEED = ["speed_vertical(mph)", "speed_vertical(kph)"]
COL_BATT_PCT = ["battery_percent", "batteryPercent", "BATTERY.chargeLevel"]
COL_VOLT = ["voltage(v)", "voltage(volts)", "BATTERY.voltage [V]"]
COL_GPS = ["gps_satellites", "satellites", "OSD.gpsNum"]
COL_MOTOR_RPM = [f"motor{i}_rpm" for i in range(1, 5)]


@dataclass
class FlightSummary:
    duration_min: Optional[float] = None
    max_height_m: Optional[float] = None
    max_distance_m: Optional[float] = None
    max_horiz_speed: Optional[float] = None
    max_vert_speed: Optional[float] = None
    battery_start: Optional[float] = None
    battery_end: Optional[float] = None
    voltage_start: Optional[float] = None
    voltage_end: Optional[float] = None
    gps_avg: Optional[float] = None
    gps_min: Optional[float] = None
    motor_means: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def battery_delta(self) -> Optional[float]:
        if self.battery_start is not None and self.battery_end is not None:
            return self.battery_start - self.battery_end
        return None


def _first_present(df, candidates) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def analyze_csv(path: Path | str) -> FlightSummary:
    """Analyze a flight CSV and return a structured summary."""
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError("pandas is required. pip install pandas") from e
    p = Path(path)
    df = pd.read_csv(p, low_memory=False)
    s = FlightSummary()

    if c := _first_present(df, COL_TIME):
        try:
            d = float(df[c].max()) - float(df[c].min())
            s.duration_min = d / 1000 / 60 if d > 1000 else d / 60
        except Exception:
            pass

    if c := _first_present(df, COL_HEIGHT):
        s.max_height_m = float(df[c].max())
        if "feet" in c:
            s.max_height_m *= 0.3048

    if c := _first_present(df, COL_DIST):
        s.max_distance_m = float(df[c].max())
        if "feet" in c:
            s.max_distance_m *= 0.3048

    if c := _first_present(df, COL_HSPEED):
        s.max_horiz_speed = float(df[c].max())

    if c := _first_present(df, COL_VSPEED):
        s.max_vert_speed = float(df[c].abs().max())

    if c := _first_present(df, COL_BATT_PCT):
        ser = df[c].dropna()
        if not ser.empty:
            s.battery_start = float(ser.iloc[0])
            s.battery_end = float(ser.iloc[-1])

    if c := _first_present(df, COL_VOLT):
        ser = df[c].dropna()
        if not ser.empty:
            s.voltage_start = float(ser.iloc[0])
            s.voltage_end = float(ser.iloc[-1])

    if c := _first_present(df, COL_GPS):
        s.gps_avg = float(df[c].mean())
        s.gps_min = float(df[c].min())
        if s.gps_min < 10:
            s.warnings.append(f"GPS dropped below 10 satellites (min={s.gps_min:.0f})")

    motor_cols = [c for c in COL_MOTOR_RPM if c in df.columns]
    if len(motor_cols) == 4:
        means = df[motor_cols].mean()
        s.motor_means = {c: float(v) for c, v in means.items()}
        spread = means.max() - means.min()
        if means.mean() > 0 and spread > means.mean() * 0.05:
            s.warnings.append(f"Motor RPM spread {spread:.0f} exceeds 5% of average")

    if (b_delta := s.battery_delta()) and b_delta > 85:
        s.warnings.append(f"Battery delta {b_delta:.0f}% — unusually high (wind or aged battery?)")
    if s.voltage_start and s.voltage_end:
        v_drop = s.voltage_start - s.voltage_end
        used = s.battery_delta() or 0.0
        # A voltage sag is only anomalous if it's DISPROPORTIONATE to the capacity
        # used — a healthy pack drops voltage roughly in step with state-of-charge, so
        # a full discharge legitimately drops >1 V. Flag it only when the pack sagged a
        # lot for little capacity used (a failing-cell signature).
        if v_drop > 1.0 and (used <= 0 or v_drop / used > 0.08):
            s.warnings.append(
                f"Voltage drop {v_drop:.2f} V disproportionate to {used:.0f}% used — inspect cells"
            )

    return s
