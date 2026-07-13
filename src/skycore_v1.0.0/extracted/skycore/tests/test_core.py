"""
SkyCore Security - Basic Test Suite
Run with: pytest tests/ -v
"""

import pytest
from core.drone import SimulatorDrone, GeoPoint
from missions.orbit import generate_orbit_mission
from cuas.threat_detector import ThreatDetector
from security.zero_trust import ZeroTrustSecurity
from security.immutable_audit import ImmutableAuditLog

def test_simulator_drone():
    drone = SimulatorDrone()
    assert drone is not None

def test_orbit_mission_generation():
    poi = GeoPoint(32.0853, 34.7818)
    df = generate_orbit_mission(poi, radius_m=50, waypoints=8)
    assert len(df) == 8
    assert 'latitude' in df.columns

def test_threat_detector():
    detector = ThreatDetector()
    detection = {"id": "TEST-001", "type": "Unknown", "position": (32.1, 34.8), "altitude": 40, "speed": 25}
    threat = detector.analyze_detection(detection)
    assert threat is not None
    assert threat.threat_level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

def test_zero_trust():
    zt = ZeroTrustSecurity()
    zt.register_entity("OPERATOR-01", "Mission Commander", ["all"])
    assert zt.enforce_least_privilege("OPERATOR-01", "all") == True

def test_immutable_audit():
    audit = ImmutableAuditLog()
    audit.add_event("TEST_EVENT", {"data": "test"}, "SYSTEM")
    assert len(audit.chain) == 1
    assert audit.verify_chain() == True
