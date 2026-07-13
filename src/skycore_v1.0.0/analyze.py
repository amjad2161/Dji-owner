"""DJI flight log analyzer.

Reads a CSV exported from Airdata UAV (or DatCon-converted DJI .DAT) and prints
a one-page health summary.

Usage:
    python analyze.py path/to/flight.csv

The script tries multiple column-name spellings since Airdata, DatCon, and DJI
Fly all differ slightly. Missing optional columns are skipped quietly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


COL_TIME = ["time(millisecond)", "time(ms)", "time", "OSD.flyTime [s]"]
COL_HEIGHT = [
    "height_above_takeoff(feet)",
    "height_above_takeoff(meters)",
    "OSD.height [m]",
    "altitude(feet)",
    "altitude(meters)",
]
COL_DIST = ["distance(feet)", "distance(meters)", "OSD.hSpeed [m/s]"]
COL_HSPEED = [
    "speed_horizontal(mph)",
    "speed_horizontal(kph)",
    "speed(mph)",
    "OSD.hSpeed [m/s]",
]
COL_VSPEED = [
    "speed_vertical(mph)",
    "speed_vertical(kph)",
    "OSD.vpsHeight [m]",
]
COL_BATT_PCT = ["battery_percent", "batteryPercent", "BATTERY.chargeLevel"]
COL_VOLT = ["voltage(v)", "voltage(volts)", "BATTERY.voltage [V]"]
COL_GPS = ["gps_satellites", "satellites", "OSD.gpsNum"]
COL_MOTOR_RPM = [f"motor{i}_rpm" for i in range(1, 5)]


def first_present(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def main(path: Path) -> int:
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    print(f"Reading: {path}")
    df = pd.read_csv(path, low_memory=False)
    print(f"Rows: {len(df):,}    Columns: {len(df.columns)}")
    print()
    print("=" * 60)
    print(f"Flight summary  —  {path.name}")
    print("=" * 60)

    time_col = first_present(df, COL_TIME)
    if time_col:
        try:
            duration_ms = float(df[time_col].max()) - float(df[time_col].min())
            duration_min = duration_ms / 1000 / 60 if duration_ms > 1000 else duration_ms / 60
            print(f"Duration:        {duration_min:6.2f} min")
        except Exception:
            pass

    height_col = first_present(df, COL_HEIGHT)
    if height_col:
        unit = "ft" if "feet" in height_col else "m"
        print(f"Max height AGL:  {df[height_col].max():6.1f} {unit}")

    dist_col = first_present(df, ["distance(feet)", "distance(meters)"])
    if dist_col:
        unit = "ft" if "feet" in dist_col else "m"
        print(f"Max distance:    {df[dist_col].max():6.1f} {unit}")

    hspeed_col = first_present(df, COL_HSPEED)
    if hspeed_col:
        unit = "mph" if "mph" in hspeed_col else ("kph" if "kph" in hspeed_col else "m/s")
        print(f"Max horiz speed: {df[hspeed_col].max():6.1f} {unit}")

    vspeed_col = first_present(df, ["speed_vertical(mph)", "speed_vertical(kph)"])
    if vspeed_col:
        unit = "mph" if "mph" in vspeed_col else "kph"
        print(f"Max vert speed:  {df[vspeed_col].abs().max():6.1f} {unit}")

    batt_col = first_present(df, COL_BATT_PCT)
    if batt_col:
        s = df[batt_col].dropna()
        if not s.empty:
            start = s.iloc[0]
            end = s.iloc[-1]
            print(f"Battery:         {start:5.0f}% → {end:.0f}% (delta {start - end:.0f}%)")

    volt_col = first_present(df, COL_VOLT)
    if volt_col:
        s = df[volt_col].dropna()
        if not s.empty:
            print(f"Voltage:         {s.iloc[0]:5.2f} V → {s.iloc[-1]:.2f} V (delta {s.iloc[0] - s.iloc[-1]:+.2f} V)")

    gps_col = first_present(df, COL_GPS)
    if gps_col:
        avg = df[gps_col].mean()
        mn = df[gps_col].min()
        print(f"GPS satellites:  avg {avg:5.1f}, min {mn:.0f}")
        if mn < 10:
            print("  WARNING: GPS dropped below 10 satellites at some point.")

    motor_cols = [c for c in COL_MOTOR_RPM if c in df.columns]
    if len(motor_cols) == 4:
        means = df[motor_cols].mean()
        spread = means.max() - means.min()
        print("Motor RPM avg:")
        for c, v in means.items():
            print(f"   {c}: {v:6.0f}")
        if means.mean() > 0 and spread > means.mean() * 0.05:
            print(f"  WARNING: motor spread {spread:.0f} RPM exceeds 5% of average.")

    print("=" * 60)
    print()
    print("Notes:")
    print("  - Battery delta of 70-80% is normal. Larger may mean wind or aged cells.")
    print("  - Voltage drop > 0.5 V at landing is normal; larger suggests weak cells.")
    print("  - GPS satellites: aim for >12 throughout. <10 limits accuracy.")
    print("  - Motor RPM imbalance > 5% suggests prop, motor wear, or bent shaft.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze.py <path-to-flight.csv>")
        sys.exit(1)
    sys.exit(main(Path(sys.argv[1])))
