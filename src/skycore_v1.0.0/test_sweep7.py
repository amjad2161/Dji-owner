"""Tests for sweep 7 modules: validator, budget, KML/GPX, calibration,
LUT parser, SRT, mission library, sidecar manifest."""
import json
import pytest
from datetime import datetime
from pathlib import Path

from skycore import GeoPoint
from skycore.missions.waypoint import WaypointMission
from skycore.core.types import MissionStep, GeofenceConfig


# ---------- mission validator ----------

def _mission(*altitudes):
    m = WaypointMission(name="test")
    for i, a in enumerate(altitudes):
        m.append(MissionStep(target=GeoPoint(0, i * 0.0001, a), speed_mps=5))
    return m


def test_validator_passes_simple_mission():
    from skycore.validate import MissionValidator
    v = MissionValidator(max_altitude_m=120)
    r = v.validate(_mission(30, 30, 30))
    assert r.is_valid


def test_validator_blocks_excessive_altitude():
    from skycore.validate import MissionValidator, Severity
    v = MissionValidator(max_altitude_m=120)
    r = v.validate(_mission(30, 200, 30))
    assert not r.is_valid
    assert any(i.severity == Severity.ERROR and i.category == "altitude" for i in r.issues)


def test_validator_circular_geofence():
    from skycore.validate import MissionValidator
    home = GeoPoint(0, 0)
    fence = GeofenceConfig(home=home, max_radius_m=100)
    # Mission goes far east — 0.01 deg ≈ 1.1 km, well outside 100 m
    v = MissionValidator(circular_geofence=fence, max_altitude_m=120)
    m = WaypointMission(name="out")
    m.append(MissionStep(target=GeoPoint(0, 0.01, 30)))
    r = v.validate(m)
    assert not r.is_valid
    assert any(i.category == "geofence" for i in r.issues)


# ---------- budget ----------

def test_budget_distance_and_duration():
    from skycore.budget import estimate_mission_distance_m, estimate_mission_duration_s
    m = WaypointMission(name="line")
    m.append(MissionStep(target=GeoPoint(0, 0, 30), speed_mps=5))
    m.append(MissionStep(target=GeoPoint(0, 0.001, 30), speed_mps=5))
    horiz, vert = estimate_mission_distance_m(m)
    assert horiz > 100  # ~111m at equator for 0.001 deg lon
    assert vert == 0
    duration = estimate_mission_duration_s(m)
    assert duration > 0


def test_budget_battery_consumption():
    from skycore.budget import estimate_battery_consumption_pct
    from skycore.profiles import get_profile
    m = _mission(30, 30, 30)
    p = get_profile("Mavic 3 Pro")
    pct = estimate_battery_consumption_pct(m, p)
    assert 0 <= pct <= 100


# ---------- KML / GPX ----------

def test_kml_export(tmp_path):
    from skycore.export import mission_to_kml
    out = tmp_path / "m.kml"
    m = _mission(30, 30)
    mission_to_kml(m, out)
    text = out.read_text()
    assert "<kml" in text
    assert "LineString" in text
    assert "Placemark" in text


def test_gpx_export(tmp_path):
    from skycore.export import telemetry_to_gpx
    out = tmp_path / "t.gpx"
    samples = [
        {"lat": 0, "lon": 0, "alt": 0, "ts": "2026-01-01T00:00:00"},
        {"lat": 0, "lon": 0.001, "alt": 5, "ts": "2026-01-01T00:00:01"},
    ]
    telemetry_to_gpx(samples, out)
    text = out.read_text()
    assert "<gpx" in text and "<trkpt" in text


# ---------- calibration ----------

def test_calibration_recommends_after_geo_move():
    from skycore.calibration import needed_calibrations
    from skycore.calibration.prompts import DroneState, CalibrationLevel
    state = DroneState(
        last_compass_calibration_lat=37.77, last_compass_calibration_lon=-122.42,
        current_lat=51.5, current_lon=-0.12,  # moved London-ish
    )
    out = needed_calibrations(state)
    assert any(p.name == "Compass" and p.level == CalibrationLevel.REQUIRED for p in out)


def test_calibration_after_crash():
    from skycore.calibration import needed_calibrations
    from skycore.calibration.prompts import DroneState, CalibrationLevel
    out = needed_calibrations(DroneState(crashed_recently=True))
    assert any(p.name == "Vision sensors" and p.level == CalibrationLevel.REQUIRED for p in out)


# ---------- SRT ----------

def test_srt_generation(tmp_path):
    from skycore.srt import generate_srt_from_telemetry
    out = tmp_path / "t.srt"
    samples = [
        {"position": {"lat": 0, "lon": 0, "alt": 10}, "battery": {"percent": 90, "voltage": 16}, "yaw": 0, "mode": "hover", "gps": {"satellites": 14}}
        for _ in range(5)
    ]
    n = generate_srt_from_telemetry(samples, out, sample_duration_s=1.0)
    assert n == 5
    text = out.read_text()
    assert "00:00:00,000" in text
    assert "GPS" in text


# ---------- mission library ----------

def test_mission_library_save_load(tmp_path):
    from skycore.library import MissionLibrary
    db = tmp_path / "lib.db"
    m = _mission(30, 30, 40)
    with MissionLibrary(db) as lib:
        mid = lib.save(m, tags=["orbit", "test"], description="A test")
        loaded = lib.load(mid)
        assert loaded is not None
        assert len(loaded) == 3
        listed = lib.list(tag="orbit")
        assert len(listed) == 1
        assert listed[0]["description"] == "A test"
        results = lib.search("test")
        assert len(results) == 1


# ---------- sidecar manifest ----------

def test_manifest_build_and_write(tmp_path):
    from skycore.sidecar import build_manifest, write_manifest
    out = tmp_path / "manifest.json"
    sample_video = tmp_path / "video.mp4"
    sample_video.write_bytes(b"fake video")
    manifest = build_manifest(
        flight_id=42,
        drone_name="sim",
        drone_model="Mavic 3 Pro",
        operator="pilot",
        started_at=datetime(2026, 1, 1, 12, 0),
        ended_at=datetime(2026, 1, 1, 12, 15),
        videos=[sample_video],
        weather={"wind_kph": 5},
        notes="clear conditions",
    )
    assert manifest["schema"] == "skycore-flight-manifest/v1"
    assert manifest["flight_id"] == 42
    assert manifest["artifacts"]["videos"][0]["size_bytes"] == 10
    write_manifest(out, manifest)
    loaded = json.loads(out.read_text())
    assert loaded["drone"]["model"] == "Mavic 3 Pro"
