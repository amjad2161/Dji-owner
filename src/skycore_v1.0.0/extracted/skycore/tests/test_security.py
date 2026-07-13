"""
Security-focused tests
"""

import pytest
from security.advanced_zero_trust import AdvancedZeroTrust
from security.drone_ids import DroneIDS
from security.key_management import MilitaryKeyManagement

def test_advanced_zero_trust():
    zt = AdvancedZeroTrust()
    zt.register_entity("DRONE-01", "FRIENDLY", ["fly", "surveil"])
    assert zt.enforce_least_privilege("DRONE-01", "fly") == True
    assert zt.enforce_least_privilege("DRONE-01", "attack") == False

def test_drone_ids():
    ids = DroneIDS()
    ids.learn_baseline("DRONE-01", {"cpu_usage": 30, "memory": 512})
    anomalies = ids.detect_anomaly("DRONE-01", {"cpu_usage": 95, "memory": 600})
    assert len(anomalies) > 0

def test_key_management():
    km = MilitaryKeyManagement()
    key = km.generate_key("DRONE-01")
    assert len(key) == 32
    assert km.rotate_keys() == True
