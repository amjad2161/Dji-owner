"""Tests for sweep 6 modules: voice command parser, wind estimator,
competency check, OpenSky helpers (logic only — no network).
"""
from datetime import datetime, timezone

import pytest

from skycore.core.types import GeoPoint, Telemetry, FlightMode


# ---------- voice command parser ----------

def test_voice_takeoff_default():
    from skycore.voice import parse_command
    cmd = parse_command("skycore takeoff")
    assert cmd is not None
    assert cmd.action == "takeoff"
    assert cmd.args["altitude"] == 5.0


def test_voice_takeoff_with_altitude():
    from skycore.voice import parse_command
    cmd = parse_command("skycore take off 25")
    assert cmd is not None
    assert cmd.action == "takeoff"
    assert cmd.args["altitude"] == 25.0


def test_voice_land_record_photo():
    from skycore.voice import parse_command
    assert parse_command("please land").action == "land"
    assert parse_command("return to home").action == "return"
    assert parse_command("take a photo").action == "photo"
    assert parse_command("recording start").action == "record_start"
    assert parse_command("recording stop").action == "record_stop"


def test_voice_goto_with_coords():
    from skycore.voice import parse_command
    cmd = parse_command("goto 37.7749 -122.4194")
    assert cmd is not None
    assert cmd.action == "goto"
    assert cmd.args["lat"] == pytest.approx(37.7749)
    assert cmd.args["lon"] == pytest.approx(-122.4194)


def test_voice_orbit_with_radius():
    from skycore.voice import parse_command
    cmd = parse_command("orbit 100")
    assert cmd is not None
    assert cmd.action == "orbit"
    assert cmd.args["radius"] == 100.0


def test_voice_unrecognized():
    from skycore.voice import parse_command
    assert parse_command("hello world") is None
    assert parse_command("") is None


# ---------- wind estimator ----------

def _tm(yaw=0, pitch=0, roll=0, vx=0, vy=0):
    return Telemetry(
        timestamp=datetime.now(timezone.utc),
        position=GeoPoint(0, 0, 10),
        velocity_xyz=(vx, vy, 0),
        yaw_deg=yaw, pitch_deg=pitch, roll_deg=roll,
        battery_percent=80, battery_voltage=16,
        gps_satellites=14, gimbal_pitch_deg=0,
        flight_mode=FlightMode.HOVER,
    )


def test_wind_zero_when_perfectly_still():
    from skycore.wind import estimate_wind
    samples = [_tm() for _ in range(20)]
    est = estimate_wind(samples)
    assert est is not None
    assert est.speed_mps < 0.5


def test_wind_estimated_from_pitched_hover():
    """Drone hovering with steady pitch → wind estimate non-zero."""
    from skycore.wind import estimate_wind
    # Drone is pitched 10 deg into the wind (nose down/forward), facing N (yaw=0),
    # with zero ground velocity → wind blowing toward north at airspeed factor * 10.
    samples = [_tm(yaw=0, pitch=10) for _ in range(20)]
    est = estimate_wind(samples)
    assert est is not None
    assert est.speed_mps > 1.0


def test_wind_returns_none_when_too_few_samples():
    from skycore.wind import estimate_wind
    assert estimate_wind([_tm()]) is None
    assert estimate_wind([]) is None


# ---------- competency check ----------

def test_competency_default_questions():
    from skycore.pilot import CompetencyCheck
    c = CompetencyCheck()
    assert len(c.questions) >= 8
    keys = {q.key for q in c.questions}
    assert "notams" in keys
    assert "weather" in keys


def test_competency_pass_fail():
    from skycore.pilot import CompetencyCheck
    c = CompetencyCheck()
    # All True
    r = c.from_dict({q.key: True for q in c.questions})
    assert r.passed(c.questions)
    assert r.missing(c.questions) == []
    # One missing
    answers = {q.key: True for q in c.questions}
    answers["notams"] = False
    r2 = c.from_dict(answers)
    assert not r2.passed(c.questions)
    assert "notams" in r2.missing(c.questions)


# ---------- opensky logic ----------

def test_is_traffic_concern_with_inline_aircraft():
    from skycore.awareness import is_traffic_concern, Aircraft
    drone = GeoPoint(37.7749, -122.4194)
    # Aircraft 2km away, at 200m altitude (within band)
    near = Aircraft(
        icao24="abc", callsign="TEST1", origin_country="US",
        longitude=-122.4194 + 0.018, latitude=37.7749,
        baro_altitude_m=200, geo_altitude_m=200,
        on_ground=False, velocity_mps=70, heading_deg=180,
        vertical_rate_mps=0,
    )
    # Aircraft far away
    far = Aircraft(
        icao24="def", callsign="TEST2", origin_country="US",
        longitude=-120.0, latitude=37.0,
        baro_altitude_m=10000, geo_altitude_m=10000,
        on_ground=False, velocity_mps=200, heading_deg=90,
        vertical_rate_mps=0,
    )
    has, hits = is_traffic_concern(drone, drone_alt_amsl_m=100, radius_km=5, altitude_band_m=300, aircraft=[near, far])
    assert has
    assert near in hits
    assert far not in hits


def test_is_traffic_concern_ignores_on_ground():
    from skycore.awareness import is_traffic_concern, Aircraft
    drone = GeoPoint(37.0, -122.0)
    grounded = Aircraft(
        icao24="x", callsign="T", origin_country="US",
        longitude=-122.0, latitude=37.0,
        baro_altitude_m=0, geo_altitude_m=0,
        on_ground=True, velocity_mps=0, heading_deg=0,
        vertical_rate_mps=0,
    )
    has, _ = is_traffic_concern(drone, drone_alt_amsl_m=50, aircraft=[grounded])
    assert not has
