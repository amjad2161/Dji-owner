"""Regression tests for the API security hardening (CSRF, origin, input bounds).

These pin the fixes from the full code review: a page the pilot merely visits must not
be able to command the aircraft, and NaN/out-of-range coordinates must not slip past
validation (a NaN latitude would otherwise defeat the geofence, since every comparison
with NaN is False).
"""
import pytest

from skycore.adapters.simulator import SimulatorDrone
from skycore.core.types import GeoPoint, GeofenceConfig

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx2")
from fastapi.testclient import TestClient  # noqa: E402

from skycore.api.app import create_app  # noqa: E402

HOME = GeoPoint(37.7749, -122.4194)
CSRF = {"X-SkyCore": "1"}


@pytest.fixture
def client():
    app = create_app(SimulatorDrone(home=HOME), GeofenceConfig(home=HOME))
    with TestClient(app) as c:
        yield c


def test_read_routes_need_no_csrf(client):
    assert client.get("/api/health").status_code == 200


def test_mutating_route_rejected_without_csrf_header(client):
    # drive-by CSRF: a cross-site POST cannot set a non-safelisted header
    assert client.post("/api/land").status_code == 403


def test_mutating_route_allowed_with_csrf_header(client):
    assert client.post("/api/land", headers=CSRF).status_code == 200


def test_cross_origin_rejected(client):
    r = client.post("/api/land", headers={**CSRF, "Origin": "http://evil.test"})
    assert r.status_code == 403


def test_same_origin_allowed(client):
    r = client.post("/api/land", headers={**CSRF, "Origin": "http://testserver"})
    assert r.status_code == 200


def test_nan_coordinates_rejected(client):
    # raw body: json.dumps refuses NaN, but a hostile client can send it literally
    r = client.post(
        "/api/goto",
        headers={**CSRF, "Content-Type": "application/json"},
        content='{"lat":NaN,"lon":0.0}',
    )
    assert r.status_code == 422


def test_out_of_range_coordinates_rejected(client):
    assert client.post("/api/goto", headers=CSRF, json={"lat": 999, "lon": 0}).status_code == 422


def test_absurd_velocity_rejected(client):
    assert client.post("/api/velocity", headers=CSRF, json={"vx": 1e9}).status_code == 422


def test_valid_commands_still_work(client):
    assert client.post("/api/takeoff", headers=CSRF, json={"altitude": 20}).status_code == 200
    r = client.post("/api/goto", headers=CSRF, json={"lat": 37.775, "lon": -122.4194, "alt": 30})
    assert r.status_code == 200
