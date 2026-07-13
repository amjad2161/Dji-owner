"""
Mission generation tests
"""

import pytest
from missions.orbit import generate_orbit_mission, GeoPoint
from missions.lawnmower import generate_lawnmower
from missions.panorama import generate_panorama

def test_orbit_generation():
    poi = GeoPoint(32.0853, 34.7818)
    df = generate_orbit_mission(poi, radius_m=60, waypoints=12)
    assert len(df) == 12
    assert all(col in df.columns for col in ['latitude', 'longitude', 'altitude(m)'])

def test_lawnmower_generation():
    poi = (32.0853, 34.7818)
    df = generate_lawnmower(poi, width_m=100, length_m=150)
    assert len(df) > 0
    assert 'latitude' in df.columns

def test_panorama_generation():
    poi = (32.0853, 34.7818)
    df = generate_panorama(poi, shots=16)
    assert len(df) == 16
    assert 'heading(deg)' in df.columns
