"""End-to-end smoke test (simulator path) using correct absolute imports.

The legacy tests/test_core.py used flat imports (`from core.drone import ...`)
that do not match the installed package layout (`skycore.core.*`), so they fail
to collect. This test exercises the REAL package — SimulatorDrone + MissionExecutor
+ GeoPoint geodesy — end to end, with no third-party deps beyond the stdlib.

Run:
    PYTHONPATH=C:\\Users\\Mobar\\SkyCore  python -m pytest skycore/tests/test_smoke_e2e.py -q
"""
from __future__ import annotations

import asyncio

from skycore.core.types import GeoPoint, FlightMode
from skycore.adapters.simulator import SimulatorDrone
from skycore.missions.executor import MissionExecutor, MissionWaypoint, MissionState


def _orbit_waypoints(poi: GeoPoint, radius_m: float, alt_m: float, n: int) -> list[MissionWaypoint]:
    """Build N evenly-spaced orbit waypoints around a POI using real geodesy."""
    wps = []
    for i in range(n):
        bearing = 360.0 * i / n
        p = poi.offset_m(radius_m, bearing, alt_delta=alt_m)
        wps.append(MissionWaypoint(lat=p.lat, lon=p.lon, alt=p.alt, speed_mps=8.0))
    return wps


def test_geopoint_geodesy_roundtrip():
    """offset_m then haversine_m must agree to <1% over short ranges."""
    home = GeoPoint(32.0853, 34.7818, 0.0)
    east = home.offset_m(100.0, 90.0)
    d = home.haversine_m(east)
    assert abs(d - 100.0) < 1.0, f"expected ~100m, got {d:.2f}m"
    assert 80.0 < home.bearing_to(east) < 100.0


def test_orbit_mission_e2e():
    """Fly an orbit mission on the simulator and verify completion + RTH."""

    async def scenario() -> dict:
        home = GeoPoint(32.0853, 34.7818, 0.0)
        poi = home.offset_m(30.0, 90.0)  # 30 m east
        # Small/fast geometry: sim wall-time ~= distance / speed (tick rate only
        # changes granularity, not wall-clock), so keep distances short.
        wps = _orbit_waypoints(poi, radius_m=8.0, alt_m=12.0, n=6)
        for w in wps:
            w.speed_mps = 30.0

        # High tick rate so the deterministic kinematics run fast in CI.
        # NOTE: skycore.core.drone.Drone (package) lacks the __aenter__/__aexit__
        # async-context-manager that the root-level drone.py defines — a real
        # inconsistency between the two base classes. Use explicit connect/
        # disconnect so the test is robust regardless.
        drone = SimulatorDrone(home=home, tick_hz=400.0)
        await drone.connect()
        try:
            await drone.takeoff(12.0)
            execu = MissionExecutor(drone)
            assert execu.load_mission(wps) is True
            assert execu.total_distance_m > 0

            await execu.start()
            # Poll for completion (bounded ~60 s wall-clock).
            for _ in range(6000):
                if execu.state in (MissionState.COMPLETED, MissionState.ABORTED):
                    break
                await asyncio.sleep(0.01)

            tele_after_mission = await drone.get_telemetry()
            await drone.return_to_home()
            tele_home = await drone.get_telemetry()
            return {
                "state": execu.state,
                "done": execu.waypoints_completed,
                "n": len(wps),
                "batt": tele_after_mission.battery_percent,
                "home_dist": home.haversine_m(tele_home.position),
                "mode": tele_home.flight_mode,
            }
        finally:
            await drone.disconnect()

    r = asyncio.run(scenario())

    assert r["state"] == MissionState.COMPLETED, f"mission state={r['state']}"
    assert r["done"] == r["n"], f"completed {r['done']}/{r['n']} waypoints"
    assert r["batt"] < 100.0, "battery should have drained during flight"
    assert r["home_dist"] < 2.0, f"RTH did not return home (dist={r['home_dist']:.2f}m)"
    assert r["mode"] == FlightMode.GROUND, f"expected GROUND after RTH, got {r['mode']}"
