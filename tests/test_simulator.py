"""Sanity tests for the simulator backend and core types."""
import asyncio
import pytest

from skycore import GeoPoint, SimulatorDrone, FlightMode
from skycore.missions import orbit_mission, lawnmower_mission, export_litchi_csv, import_litchi_csv


@pytest.mark.asyncio
async def test_simulator_takeoff_and_land():
    drone = SimulatorDrone(home=GeoPoint(0, 0), tick_hz=50.0)
    await drone.connect()
    assert drone.is_connected
    await drone.takeoff(altitude_m=10.0)
    tm = await drone.get_telemetry()
    assert tm.position.alt == pytest.approx(10.0, abs=1.0)
    assert tm.flight_mode == FlightMode.HOVER
    await drone.land()
    tm = await drone.get_telemetry()
    assert tm.position.alt == pytest.approx(0.0, abs=0.5)
    await drone.disconnect()


@pytest.mark.asyncio
async def test_simulator_goto_distance():
    home = GeoPoint(37.7749, -122.4194)
    drone = SimulatorDrone(home=home, tick_hz=50.0)
    await drone.connect()
    await drone.takeoff(20)
    target = home.offset_m(100, 90, alt_delta=20)  # 100m east of home
    await drone.goto(target, speed_mps=10)
    tm = await drone.get_telemetry()
    assert home.haversine_m(tm.position) == pytest.approx(100.0, abs=2.0)
    await drone.disconnect()


def test_geopoint_haversine_and_bearing():
    a = GeoPoint(0, 0)
    b = GeoPoint(0, 1)  # 1° east at equator ≈ 111 km
    assert a.haversine_m(b) == pytest.approx(111_195, rel=0.001)
    assert a.bearing_to(b) == pytest.approx(90.0, abs=0.1)


def test_geopoint_offset_roundtrip():
    a = GeoPoint(37.7749, -122.4194)
    b = a.offset_m(500, 45)
    assert a.haversine_m(b) == pytest.approx(500, rel=0.005)
    assert a.bearing_to(b) == pytest.approx(45, abs=0.5)


def test_orbit_mission_geometry():
    poi = GeoPoint(37.7749, -122.4194)
    m = orbit_mission(poi, radius_m=50, waypoints=12, altitude_m=30)
    assert len(m) == 12
    for step in m.steps:
        assert poi.haversine_m(step.target) == pytest.approx(50, rel=0.05)
        assert step.target.alt == pytest.approx(30)


def test_lawnmower_covers_box():
    sw = GeoPoint(37.7700, -122.4200)
    ne = GeoPoint(37.7710, -122.4180)
    m = lawnmower_mission(sw, ne, altitude_m=50, sensor_width_m_at_altitude=70)
    assert len(m) >= 4  # at least 2 lines (4 waypoints)


def test_litchi_csv_roundtrip(tmp_path):
    poi = GeoPoint(37.7749, -122.4194)
    m = orbit_mission(poi, radius_m=30, waypoints=8, altitude_m=20)
    p = tmp_path / "orbit.csv"
    export_litchi_csv(m, p, poi=poi)
    m2 = import_litchi_csv(p)
    assert len(m2) == len(m)
    for s1, s2 in zip(m.steps, m2.steps):
        assert s1.target.lat == pytest.approx(s2.target.lat, abs=1e-5)
        assert s1.target.lon == pytest.approx(s2.target.lon, abs=1e-5)
