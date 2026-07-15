"""More tests for sweep 5 modules: checklist, templates, profiles, events, battery."""
import pytest

from skycore import GeoPoint, SimulatorDrone


# ---------- checklist ----------

@pytest.mark.asyncio
async def test_checklist_simulator_passes_basic():
    from skycore.checklist import PreflightChecklist, ItemStatus
    drone = SimulatorDrone(home=GeoPoint(0, 0), tick_hz=50)
    await drone.connect()
    cl = PreflightChecklist(drone=drone, min_battery_percent=50, min_gps_satellites=12)
    report = await cl.run()
    statuses = {i.name: i.status for i in report.items}
    assert statuses.get("Connectivity") == ItemStatus.PASS
    assert statuses.get("Telemetry") == ItemStatus.PASS
    assert statuses.get("Battery") == ItemStatus.PASS
    assert statuses.get("GPS") == ItemStatus.PASS
    assert report.ok is True
    await drone.disconnect()


@pytest.mark.asyncio
async def test_checklist_extra_check_runs():
    from skycore.checklist import PreflightChecklist, ChecklistItem, ItemStatus
    cl = PreflightChecklist()
    async def custom():
        return ChecklistItem("custom", ItemStatus.PASS, "all good")
    cl.add_check(custom)
    report = await cl.run()
    assert any(i.name == "custom" for i in report.items)


# ---------- templates ----------

def test_panorama_yields_grid():
    from skycore.templates import panorama_mission
    m = panorama_mission(GeoPoint(0, 0), yaw_steps=8, photos_per_yaw=3, gimbal_pitches=(-15, -45, -75))
    assert len(m) == 24


def test_perimeter_patrol_traces_polygon():
    from skycore.templates import perimeter_patrol
    pts = [
        GeoPoint(0, 0), GeoPoint(0, 0.001), GeoPoint(0.001, 0.001), GeoPoint(0.001, 0)
    ]
    m = perimeter_patrol(pts, altitude_m=30)
    assert len(m) >= len(pts)


def test_building_inspection_stacks():
    from skycore.templates import building_inspection
    m = building_inspection(GeoPoint(0, 0), radius_m=20, altitudes_m=(10, 20), waypoints_per_ring=8)
    assert len(m) == 16


def test_hyperlapse_line_evenly_spaced():
    from skycore.templates import hyperlapse_line
    a = GeoPoint(0, 0)
    b = GeoPoint(0, 0.01)
    m = hyperlapse_line(a, b, photos=10)
    assert len(m) == 10
    assert m.steps[0].target.lat == pytest.approx(0)
    assert m.steps[-1].target.lon == pytest.approx(0.01)


def test_cinematic_reveal_two_waypoints():
    from skycore.templates import cinematic_reveal
    m = cinematic_reveal(GeoPoint(0, 0), GeoPoint(0.001, 0))
    assert len(m) == 2
    assert "start_record" in m.steps[0].actions
    assert "stop_record" in m.steps[1].actions


# ---------- profiles ----------

def test_drone_profile_lookup():
    from skycore.profiles import get_profile
    p = get_profile("Mavic 3 Pro")
    assert p is not None
    assert p.weight_g == 958
    assert p.has_d_log
    p2 = get_profile("mini 4 pro")
    assert p2 is not None
    assert p2.weight_g == 249


def test_unknown_profile_returns_none():
    from skycore.profiles import get_profile
    assert get_profile("phantom 99") is None


# ---------- events ----------

@pytest.mark.asyncio
async def test_event_emitter_dispatches_by_type():
    from skycore.events import EventEmitter, TakeoffComplete, BatteryWarning
    e = EventEmitter()
    seen = []
    async def on_takeoff(ev):
        seen.append(("takeoff", ev.altitude_m))
    async def on_warning(ev):
        seen.append(("battery", ev.percent))
    e.on(TakeoffComplete, on_takeoff)
    e.on(BatteryWarning, on_warning)

    await e.emit(TakeoffComplete(drone_name="sim", altitude_m=10))
    await e.emit(BatteryWarning(drone_name="sim", percent=20.0, threshold=25.0))

    assert ("takeoff", 10) in seen
    assert ("battery", 20.0) in seen


# ---------- battery ----------

def test_battery_registry_health_progresses(tmp_path):
    from skycore.battery import BatteryRegistry, BatteryRecord
    db = tmp_path / "b.db"
    with BatteryRegistry(db) as reg:
        reg.register(BatteryRecord(serial="BAT001", nominal_capacity_mah=5000))
        # 10 normal cycles
        for i in range(10):
            cid = reg.start_cycle("BAT001", 100)
            reg.end_cycle(cid, 30, 14.5)
        # 5 heavy discharge cycles
        for i in range(5):
            cid = reg.start_cycle("BAT001", 100)
            reg.end_cycle(cid, 5, 13.2)
        h = reg.get_health("BAT001")
        assert h is not None
        assert h.cycles == 15
        assert h.heavy_discharge_count == 5
        assert h.estimated_health_pct < 100.0
        assert h.estimated_health_pct > 95.0  # only 15 cycles, still healthy
