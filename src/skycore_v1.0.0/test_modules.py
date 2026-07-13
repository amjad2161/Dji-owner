"""Sanity tests for the new modules.

Network-dependent paths (Open-Meteo, Open-Elevation) are not exercised here
— they're tested by integration tests outside CI. We test the *logic*:
local mission generation, geofence math, planning correctness, formation
offsets, SQLite round-trip, replay parsing.
"""
import asyncio
import pytest
from pathlib import Path

from skycore import GeoPoint, SimulatorDrone
from skycore.core.event_bus import EventBus


# ---------- geofence ----------

def test_polygon_geofence_contains():
    pytest.importorskip("shapely")
    from skycore.geofence import PolygonGeofence

    # Square around (0, 0) with side ~0.001 deg
    poly = PolygonGeofence(
        points=[(0.001, 0.001), (0.001, -0.001), (-0.001, -0.001), (-0.001, 0.001)],
        name="square",
    )
    assert poly.contains(GeoPoint(0, 0))
    assert not poly.contains(GeoPoint(0.005, 0.005))


def test_polygon_geofence_inverted():
    pytest.importorskip("shapely")
    from skycore.geofence import PolygonGeofence

    poly = PolygonGeofence(
        points=[(0.001, 0.001), (0.001, -0.001), (-0.001, -0.001), (-0.001, 0.001)],
        inverted=True,
    )
    assert not poly.contains(GeoPoint(0, 0))  # inside the no-fly polygon
    assert poly.contains(GeoPoint(0.005, 0.005))  # outside is OK


# ---------- planning ----------

def test_astar_avoids_obstacle():
    pytest.importorskip("shapely")
    from skycore.planning import plan_around_obstacles

    start = GeoPoint(0, 0)
    end = GeoPoint(0.001, 0)
    # Block a square in the middle of the direct path
    obstacle = [
        (0.0003, -0.00005), (0.0003, 0.00005),
        (0.0007, 0.00005), (0.0007, -0.00005),
    ]
    path = plan_around_obstacles(start, end, [obstacle], grid_resolution_m=15.0)
    assert len(path) >= 2
    assert path[0].haversine_m(start) < 30
    assert path[-1].haversine_m(end) < 30


# ---------- fleet ----------

def test_line_formation():
    from skycore.fleet import line_formation

    offsets = line_formation(3, spacing_m=10)
    rights = [o.right for o in offsets]
    assert rights == [-10, 0, 10]


def test_v_formation():
    from skycore.fleet import v_formation

    offsets = v_formation(5, spacing_m=10)
    assert offsets[0].forward == 0 and offsets[0].right == 0
    # First follower goes back and to one side
    assert offsets[1].forward < 0


@pytest.mark.asyncio
async def test_fleet_synchronized_takeoff_and_land():
    from skycore.fleet import Fleet
    drones = [SimulatorDrone(home=GeoPoint(0, 0), tick_hz=50) for _ in range(3)]
    fleet = Fleet(drones)
    await fleet.connect_all()
    await fleet.takeoff_all(altitude_m=5)
    for d in drones:
        tm = await d.get_telemetry()
        assert tm.position.alt == pytest.approx(5.0, abs=0.5)
    await fleet.land_all()
    await fleet.disconnect_all()


# ---------- storage ----------

def test_sqlite_flight_roundtrip(tmp_path):
    from skycore.storage import FlightDatabase

    db = tmp_path / "flights.db"
    with FlightDatabase(db) as fdb:
        fid = fdb.start_flight("sim", 37.7, -122.4)
        assert fid > 0
        fdb.record_telemetry(fid, {
            "timestamp": "2026-01-01T00:00:00",
            "position": {"lat": 37.7, "lon": -122.4, "alt": 30},
            "battery": {"percent": 90, "voltage": 16.5},
            "yaw": 90,
        })
        fdb.commit()
        fdb.end_flight(fid, {"max_alt": 30, "duration_min": 5})
        flights = fdb.list_flights()
        assert len(flights) == 1
        assert flights[0]["summary"]["max_alt"] == 30
        tm = fdb.get_telemetry(fid)
        assert len(tm) == 1
        assert tm[0]["yaw"] == 90


# ---------- replay ----------

@pytest.mark.asyncio
async def test_replay_csv_publishes_to_bus(tmp_path):
    import csv
    from skycore.replay import replay_csv
    from skycore.core.event_bus import EventBus

    csv_path = tmp_path / "r.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time(millisecond)", "latitude", "longitude", "height_above_takeoff(meters)", "battery_percent", "compass_heading(degrees)"])
        w.writerow([0, 37.7749, -122.4194, 0, 100, 0])
        w.writerow([100, 37.7749, -122.4194, 5, 99, 10])
        w.writerow([200, 37.7749, -122.4194, 10, 98, 20])

    bus = EventBus()
    q = bus.subscribe("telemetry")
    task = asyncio.create_task(replay_csv(csv_path, bus, speedup=1000.0))
    received = []
    for _ in range(3):
        received.append(await asyncio.wait_for(q.get(), timeout=2.0))
    await task
    assert len(received) == 3
    assert received[2]["position"]["alt"] == 10.0
    assert received[1]["yaw"] == 10.0


# ---------- KML / GeoJSON loading ----------

def test_geojson_polygon_roundtrip(tmp_path):
    pytest.importorskip("shapely")
    from skycore.geofence import load_geojson
    import json

    p = tmp_path / "area.geojson"
    p.write_text(json.dumps({
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-122.42, 37.77], [-122.41, 37.77], [-122.41, 37.78], [-122.42, 37.78], [-122.42, 37.77]
            ]]
        }
    }))
    g = load_geojson(p)
    assert len(g.points) == 5
    assert g.contains(GeoPoint(37.775, -122.415))
    assert not g.contains(GeoPoint(37.78, -122.40))
