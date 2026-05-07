"""Sanity tests for analytics module."""
import pandas as pd
import pytest
from pathlib import Path

from skycore.analytics.log_analyzer import analyze_csv


def test_analyze_csv_minimal(tmp_path):
    csv = tmp_path / "flight.csv"
    df = pd.DataFrame({
        "time(millisecond)": [0, 1000, 5000, 60000],
        "height_above_takeoff(meters)": [0, 5, 50, 30],
        "distance(meters)": [0, 5, 100, 80],
        "speed_horizontal(kph)": [0, 5, 30, 10],
        "battery_percent": [98, 95, 50, 30],
        "voltage(v)": [17.4, 17.0, 15.5, 14.8],
        "gps_satellites": [16, 17, 18, 16],
    })
    df.to_csv(csv, index=False)

    s = analyze_csv(csv)
    assert s.duration_min == pytest.approx(1.0, abs=0.01)
    assert s.max_height_m == 50.0
    assert s.max_distance_m == 100.0
    assert s.battery_start == 98
    assert s.battery_end == 30
    assert s.gps_min == 16
    assert not s.warnings  # no anomalies in this data
