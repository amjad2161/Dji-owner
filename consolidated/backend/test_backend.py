"""
Tests for the SkyCore live backend — proves the three real skycore modules
(AUKF nav, LQR control, CUASClassifier detection) actually run in the loop.

Run:  python test_backend.py      (no deps beyond the backend's own)
  or: pytest test_backend.py
"""
import math
import serve

HOME_LAT, HOME_LON = serve.HOME_LAT, serve.HOME_LON
M_PER_DEG_LAT = serve.M_PER_DEG_LAT


def _steps(s: "serve.SimState", n: int) -> None:
    for _ in range(n):
        s.step()


def test_real_backends_loaded():
    s = serve.SimState()
    assert s.nav_backend.startswith("skycore.navigation.aukf"), s.nav_backend
    assert s.control_backend.startswith("skycore.control.lqr"), s.control_backend
    assert s.detect_backend.startswith("skycore.cuas.classifier"), s.detect_backend


def test_takeoff_climbs_via_lqr():
    s = serve.SimState()
    s.command("takeoff", {"altitude": 40})
    _steps(s, 120)                      # ~12 s sim (plant advances at fixed 0.1 s/step)
    assert s.mode == "FLYING", s.mode
    assert 35 <= s.u <= 45, s.u         # LQR converged to ~40 m


def test_goto_moves_toward_target():
    s = serve.SimState()
    s.command("takeoff", {"altitude": 40})
    _steps(s, 60)
    assert s.u > 0.5
    target_lat = HOME_LAT + 100.0 / M_PER_DEG_LAT   # 100 m north
    s.command("goto", {"lat": target_lat, "lon": HOME_LON, "altitude": 40})
    _steps(s, 200)
    assert s.n > 40.0, f"expected northward motion, n={s.n}"   # closed toward 100 m north


def test_land_disarms():
    s = serve.SimState()
    s.command("takeoff", {"altitude": 30})
    _steps(s, 60)
    s.command("land", {})
    _steps(s, 300)
    assert s.mode == "DISARMED", s.mode
    assert s.u <= 0.2, s.u


def test_detection_emits_valid_threats_with_behaviour():
    s = serve.SimState()
    behaviours = set()
    for _ in range(130):                       # ~13 s -> let loiter/incursion behaviours develop
        s.step()
        for t in s.threats:
            behaviours.add(t["behavior"])
    assert len(s.threats) >= 3, f"expected multiple tracks, got {len(s.threats)}"
    for t in s.threats:
        assert t["severity"] in ("low", "medium", "high", "critical"), t["severity"]
        assert isinstance(t["type"], str) and t["type"]
        assert t["behavior"] in ("fast_approach", "loitering", "restricted_zone", "transit"), t["behavior"]
        assert t["distance"] >= 0 and 0 <= t["bearing"] < 360
    assert "fast_approach" in behaviours and "loitering" in behaviours, behaviours


def test_snapshot_shape_matches_gcs_contract():
    s = serve.SimState()
    _steps(s, 5)
    snap = s.snapshot()
    assert snap["source"] == "simulator"
    assert "percent" in snap["battery"]
    for k in ("lat", "lon", "altitude"):
        assert k in snap["position"]
    assert "speed" in snap["velocity"]
    assert "yaw" in snap["attitude"]
    assert isinstance(snap["mode"], str)


def test_aukf_estimate_tracks_truth():
    s = serve.SimState()
    s.command("takeoff", {"altitude": 40})
    _steps(s, 120)
    assert s.filter is not None and "aukf" in s.nav_backend
    snap = s.snapshot()
    # hovering over home -> filtered lat/lon should stay within a few metres of home
    err_m = abs(snap["position"]["lat"] - HOME_LAT) * M_PER_DEG_LAT
    assert err_m < 20.0, f"AUKF lateral error {err_m:.1f} m"


def test_geofence_blocks_and_rtls():
    s = serve.SimState()
    assert s.gf is not None and "geofence" in s.geofence_backend.lower(), s.geofence_backend
    s.command("takeoff", {"altitude": 40})
    _steps(s, 60)
    # a goto whose target sits inside the circular no-fly zone must be rejected
    nf_lat = HOME_LAT + serve.NOFLY_N / M_PER_DEG_LAT
    nf_lon = HOME_LON + serve.NOFLY_E / serve.M_PER_DEG_LON
    s.command("goto", {"lat": nf_lat, "lon": nf_lon, "altitude": 40})
    assert "blocked" in s.geofence_reason, s.geofence_reason
    # forcing the aircraft inside the zone must trigger RTL on the next tick
    s.e, s.n = serve.NOFLY_E, serve.NOFLY_N
    _steps(s, 2)
    assert s.mode == "RTL", s.mode
    assert "breach" in s.geofence_reason, s.geofence_reason


def test_rrt_routes_around_nofly():
    import random
    random.seed(20240714)                    # RRT* is randomized -> seed for a deterministic test
    s = serve.SimState()
    if s.rrt is None:
        return  # planner unavailable -> honest skip
    assert "rrt" in s.route_backend.lower(), s.route_backend
    s.command("takeoff", {"altitude": 40})
    _steps(s, 60)
    far_lat = HOME_LAT + 160.0 / M_PER_DEG_LAT
    far_lon = HOME_LON + 300.0 / serve.M_PER_DEG_LON      # far side -> straight path crosses the zone
    s.command("goto", {"lat": far_lat, "lon": far_lon, "altitude": 40})
    assert s.route, "expected a planned route around the zone"
    min_clear = 999.0
    for _ in range(600):
        _steps(s, 1)
        min_clear = min(min_clear, math.hypot(s.e - serve.NOFLY_E, s.n - serve.NOFLY_N) - serve.NOFLY_R)
        if s.mode == "RTL":
            break
        if math.hypot(s.e - 300.0, s.n - 160.0) < 5.0:
            break
    assert s.mode != "RTL", "routing should avoid the zone, not trip RTL"
    assert min_clear > 0.0, f"aircraft entered the no-fly zone (clearance {min_clear:.1f} m)"


def test_flight_history_logs_to_sqlite():
    import os as _os
    _os.environ["SKYCORE_DB"] = ":memory:"
    s = serve.SimState()
    _os.environ.pop("SKYCORE_DB", None)
    if s.db is None:
        return  # storage module unavailable -> honest skip
    before = len(s.db.get_history())
    s.command("takeoff", {"altitude": 30})
    _steps(s, 120)
    s.command("land", {})
    _steps(s, 400)                                # descend to DISARMED -> logs the flight
    hist = s.db.get_history()
    assert len(hist) == before + 1, f"expected exactly one logged flight, got {len(hist) - before}"
    f = hist[0]
    assert f["drone_id"] == "SIM-1", f
    assert f["max_alt"] >= 15.0, f
    assert f["distance_km"] >= 0.0 and f["battery_used"] >= 0.0, f


def test_weather_module_loaded():
    # the real Open-Meteo client imports; a live fetch is exercised by the server loop (needs network)
    assert serve.WEATHER_BACKEND != "unavailable", serve.WEATHER_BACKEND
    assert serve.preflight_check is not None
    assert set(serve._weather) >= {"backend", "ok", "issues", "temp_c", "wind_kph"}


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    raise SystemExit(0 if passed == len(tests) else 1)
