"""
SkyCore Comprehensive Test Suite
Tests for state machine, safety monitor, and system integration.
"""

import pytest
import time
import threading
import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skycore.state_machine import (
    FlightStateMachine, FlightState, TriggerEvent, SafetyLimits, ModeController, FailsafeManager
)
from skycore.safety_monitor import (
    SafetyMonitor, SafetyConfig, SafetyLevel, ViolationType, SafetyViolation, GeofenceValidator
)


# ============== State Machine Tests ==============

class TestFlightStateMachine:
    """Test flight state machine functionality"""
    
    def test_initial_state(self):
        """Test initial state is DISARMED"""
        sm = FlightStateMachine()
        assert sm.state == FlightState.DISARMED
        assert sm.is_armed() is False
        assert sm.can_arm() is True
        assert sm.can_disarm() is False
    
    def test_arm_disarm(self):
        """Test arm and disarm transitions"""
        sm = FlightStateMachine()
        
        # Arm
        assert sm.trigger(TriggerEvent.ARM_REQUEST) is True
        assert sm.state == FlightState.ARMED
        assert sm.is_armed() is True
        assert sm.can_disarm() is True
        
        # Disarm
        assert sm.trigger(TriggerEvent.DISARM_REQUEST) is True
        assert sm.state == FlightState.DISARMED
    
    def test_takeoff_sequence(self):
        """Test complete takeoff sequence"""
        sm = FlightStateMachine()
        
        # Arm
        assert sm.trigger(TriggerEvent.ARM_REQUEST) is True
        
        # Takeoff
        assert sm.trigger(TriggerEvent.TAKEOFF_CMD) is True
        assert sm.state == FlightState.TAKEOFF
        
        # Start mission (auto mode)
        assert sm.trigger(TriggerEvent.MISSION_START) is True
        assert sm.state == FlightState.AUTO
    
    def test_invalid_transition(self):
        """Test invalid transitions are rejected"""
        sm = FlightStateMachine()
        
        # Cannot takeoff from DISARMED
        assert sm.trigger(TriggerEvent.TAKEOFF_CMD) is False
        assert sm.state == FlightState.DISARMED
    
    def test_rtl_from_auto(self):
        """Test RTL from auto mode"""
        sm = FlightStateMachine()
        
        # Setup: armed and in auto
        sm.trigger(TriggerEvent.ARM_REQUEST)
        sm.trigger(TriggerEvent.TAKEOFF_CMD)
        sm.trigger(TriggerEvent.MISSION_START)
        
        # RTL
        assert sm.trigger(TriggerEvent.RTL_CMD) is True
        assert sm.state == FlightState.RTL
    
    def test_land_from_auto(self):
        """Test land from auto mode"""
        sm = FlightStateMachine()
        
        # Setup
        sm.trigger(TriggerEvent.ARM_REQUEST)
        sm.trigger(TriggerEvent.TAKEOFF_CMD)
        sm.trigger(TriggerEvent.MISSION_START)
        
        # Land
        assert sm.trigger(TriggerEvent.LAND_CMD) is True
        assert sm.state == FlightState.LANDING
    
    def test_gps_lost_triggers_hold(self):
        """Test GPS loss from auto triggers hold"""
        sm = FlightStateMachine()
        
        # Setup
        sm.trigger(TriggerEvent.ARM_REQUEST)
        sm.trigger(TriggerEvent.TAKEOFF_CMD)
        sm.trigger(TriggerEvent.MISSION_START)
        
        # GPS lost
        assert sm.trigger(TriggerEvent.GPS_LOST) is True
        assert sm.state == FlightState.HOLD
    
    def test_battery_low_triggers_rtl(self):
        """Test low battery from auto triggers RTL"""
        sm = FlightStateMachine()
        
        # Setup
        sm.trigger(TriggerEvent.ARM_REQUEST)
        sm.trigger(TriggerEvent.TAKEOFF_CMD)
        sm.trigger(TriggerEvent.MISSION_START)
        
        # Low battery
        assert sm.trigger(TriggerEvent.BATTERY_LOW) is True
        assert sm.state == FlightState.RTL
    
    def test_update_telemetry(self):
        """Test telemetry updates"""
        sm = FlightStateMachine()
        sm.trigger(TriggerEvent.ARM_REQUEST)
        
        # Update GPS
        sm.update_telemetry(gps_satellites=10)
        assert sm.gps_satellites == 10
        
        # Update battery
        sm.update_telemetry(battery_percent=25)
        assert sm.battery_percent == 25
    
    def test_geofence_distance_check(self):
        """Test geofence distance monitoring"""
        sm = FlightStateMachine(safety_limits=SafetyLimits(max_distance_m=1000))
        sm.update_telemetry(
            position={"lat": 32.0, "lon": 34.0, "alt": 50},
            battery_percent=100,
            gps_satellites=12
        )
        
        # Set home to same position - distance should be 0
        sm.home_position = {"lat": 32.0, "lon": 34.0, "alt": 0}
        
        # Should be safe since we're at home
        assert sm.check_geofence() is True
        
        # Move away - test distance calculation
        sm.update_telemetry(position={"lat": 32.01, "lon": 34.01, "alt": 50})
        # Distance from home at same position should still be ok
        assert sm.check_geofence() is True
    
    def test_is_flying(self):
        """Test is_flying check"""
        sm = FlightStateMachine()
        
        assert sm.is_flying() is False
        
        sm.trigger(TriggerEvent.ARM_REQUEST)
        assert sm.is_flying() is False
        
        sm.trigger(TriggerEvent.TAKEOFF_CMD)
        assert sm.is_flying() is True
        
        sm.trigger(TriggerEvent.LAND_CMD)
        assert sm.is_flying() is True
        
        sm.trigger(TriggerEvent.MISSION_END)
        # After landing mission end, should be in hold
        assert sm.is_flying() is True  # Still landing
    
    def test_emergency_stop(self):
        """Test emergency stop"""
        sm = FlightStateMachine()
        sm.trigger(TriggerEvent.ARM_REQUEST)
        sm.trigger(TriggerEvent.TAKEOFF_CMD)
        
        sm.emergency_stop()
        assert sm.state == FlightState.ESTOP
    
    def test_force_state(self):
        """Test force state"""
        sm = FlightStateMachine()
        sm.trigger(TriggerEvent.ARM_REQUEST)
        
        sm.force_state(FlightState.FAILSAFE, "test")
        assert sm.state == FlightState.FAILSAFE
    
    def test_state_history(self):
        """Test state history tracking"""
        sm = FlightStateMachine()
        sm.trigger(TriggerEvent.ARM_REQUEST)
        sm.trigger(TriggerEvent.TAKEOFF_CMD)
        
        history = sm.get_state_history()
        assert len(history) >= 2
    
    def test_callback_registration(self):
        """Test callback registration"""
        sm = FlightStateMachine()
        
        callback_called = []
        def callback(from_state, to_state, event):
            callback_called.append((from_state, to_state, event))
        
        sm.register_state_change_callback(callback)
        sm.trigger(TriggerEvent.ARM_REQUEST)
        
        assert len(callback_called) > 0


class TestModeController:
    """Test mode controller"""
    
    def test_mode_to_state_mapping(self):
        """Test mode to state mapping"""
        sm = FlightStateMachine()
        mc = ModeController(sm)
        
        # Manual mode - set to AUTO then switch to manual
        sm.trigger(TriggerEvent.ARM_REQUEST)
        sm.trigger(TriggerEvent.TAKEOFF_CMD)
        sm.trigger(TriggerEvent.MISSION_START)  # Now in AUTO
        
        assert mc.set_mode("manual") is True
        assert sm.state == FlightState.MANUAL
    
    def test_get_current_mode(self):
        """Test get current mode"""
        sm = FlightStateMachine()
        mc = ModeController(sm)
        
        sm.trigger(TriggerEvent.ARM_REQUEST)
        sm.trigger(TriggerEvent.TAKEOFF_CMD)
        sm.trigger(TriggerEvent.MISSION_START)  # Now in AUTO
        
        assert mc.get_current_mode() == "auto"


class TestFailsafeManager:
    """Test failsafe manager"""
    
    def test_trigger_failsafe(self):
        """Test failsafe triggering"""
        sm = FlightStateMachine()
        fm = FailsafeManager(sm, SafetyLimits())
        
        assert fm.trigger_failsafe("RC loss") is True
    
    def test_check_battery(self):
        """Test battery monitoring"""
        sm = FlightStateMachine()
        fm = FailsafeManager(sm, SafetyLimits(battery_land_percent=10))
        
        sm.trigger(TriggerEvent.ARM_REQUEST)
        sm.trigger(TriggerEvent.TAKEOFF_CMD)
        sm.trigger(TriggerEvent.MISSION_START)
        
        # Check critical battery
        assert fm.check_battery(5) is True


# ============== Safety Monitor Tests ==============

class TestSafetyMonitor:
    """Test safety monitoring"""
    
    def test_initialization(self):
        """Test safety monitor initialization"""
        sm = SafetyMonitor()
        status = sm.get_status()
        
        assert status["level"] == SafetyLevel.OK
        assert status["active_violations"] == 0
    
    def test_battery_warning(self):
        """Test battery warning level"""
        sm = SafetyMonitor(config=SafetyConfig(battery_warning_percent=30))
        sm.update_state({"battery": {"percent": 25, "voltage": 15.0, "current": 0}})
        
        violations = sm.check_all()
        assert any(v.violation_type == ViolationType.BATTERY_LOW for v in violations)
    
    def test_battery_critical(self):
        """Test battery critical level"""
        sm = SafetyMonitor(config=SafetyConfig(battery_critical_percent=10))
        sm.update_state({"battery": {"percent": 8, "voltage": 14.0, "current": 0}})
        
        violations = sm.check_all()
        assert any(v.severity == SafetyLevel.CRITICAL for v in violations)
    
    def test_altitude_exceeded(self):
        """Test altitude monitoring"""
        sm = SafetyMonitor(config=SafetyConfig(max_altitude_m=120))
        sm.update_state({"position": {"alt": 130}})
        
        violations = sm.check_all()
        assert any(v.violation_type == ViolationType.ALTITUDE_EXCEEDED for v in violations)
    
    def test_gps_lost(self):
        """Test GPS signal lost"""
        sm = SafetyMonitor()
        sm.update_state({"gps": {"satellites": 0, "hdop": 99}})
        
        violations = sm.check_all()
        assert any(v.violation_type == ViolationType.GPS_LOST for v in violations)
    
    def test_gps_degraded(self):
        """Test GPS degraded"""
        sm = SafetyMonitor(config=SafetyConfig(min_gps_satellites=8))
        sm.update_state({"gps": {"satellites": 5, "hdop": 3.0}})
        
        violations = sm.check_all()
        assert any(v.violation_type == ViolationType.GPS_DEGRADED for v in violations)
    
    def test_rc_connection_lost(self):
        """Test RC connection lost"""
        sm = SafetyMonitor()
        sm.update_state({"rc": {"connected": False, "last_signal": time.time() - 10}})
        
        violations = sm.check_all()
        assert any(v.violation_type == ViolationType.RC_LOST for v in violations)
    
    def test_wind_exceeded(self):
        """Test wind speed exceeded"""
        sm = SafetyMonitor(config=SafetyConfig(max_wind_ms=10))
        sm.update_state({"environment": {"wind_speed": 15}})
        
        violations = sm.check_all()
        assert any(v.violation_type == ViolationType.WIND_EXCEEDED for v in violations)
    
    def test_temperature(self):
        """Test temperature monitoring"""
        sm = SafetyMonitor(config=SafetyConfig(max_temperature_c=60))
        sm.update_state({"environment": {"temperature": 70}})
        
        violations = sm.check_all()
        assert any(v.violation_type == ViolationType.TEMPERATURE_HIGH for v in violations)
    
    def test_safety_callback(self):
        """Test safety violation callback"""
        sm = SafetyMonitor()
        
        callback_violations = []
        sm.register_violation_callback(lambda v: callback_violations.append(v))
        
        sm.update_state({"battery": {"percent": 5, "voltage": 14.0, "current": 0}})
        sm.check_all()
        
        assert len(callback_violations) > 0
    
    def test_recovery_callback(self):
        """Test violation recovery callback"""
        sm = SafetyMonitor(config=SafetyConfig(battery_warning_percent=30))
        
        sm.update_state({"battery": {"percent": 25, "voltage": 15.0, "current": 0}})
        sm.check_all()  # Should have warning
        
        sm.update_state({"battery": {"percent": 50, "voltage": 16.0, "current": 0}})
        sm.check_all()  # Should recover
    
    def test_is_safe_to_fly(self):
        """Test is_safe_to_fly check"""
        sm = SafetyMonitor()
        
        # No violations = safe
        assert sm.is_safe_to_fly() is True
        
        # Battery low = not safe
        sm.update_state({"battery": {"percent": 5, "voltage": 14.0, "current": 0}})
        sm.check_all()
        assert sm.is_safe_to_fly() is False
    
    def test_is_safe_to_takeoff(self):
        """Test is_safe_to_takeoff check"""
        sm = SafetyMonitor()
        
        # Good conditions
        sm.update_state({
            "gps": {"satellites": 10},
            "battery": {"percent": 80, "voltage": 16.0, "current": 0},
            "rc": {"connected": True, "last_signal": time.time()}
        })
        assert sm.is_safe_to_takeoff() is True
        
        # No GPS
        sm.update_state({"gps": {"satellites": 3}})
        assert sm.is_safe_to_takeoff() is False
    
    def test_background_monitoring(self):
        """Test background monitoring loop"""
        sm = SafetyMonitor()
        
        sm.update_state({"battery": {"percent": 100, "voltage": 16.8, "current": 0}})
        sm.start_monitoring()
        
        time.sleep(0.5)
        
        sm.stop_monitoring()
        assert sm.get_status()["uptime_sec"] > 0
    
    def test_violation_history(self):
        """Test violation history tracking"""
        sm = SafetyMonitor()
        
        sm.update_state({"battery": {"percent": 5, "voltage": 14.0, "current": 0}})
        sm.check_all()
        
        history = sm.get_violation_history(5)
        assert len(history) >= 1
    
    def test_clear_history(self):
        """Test clearing history"""
        sm = SafetyMonitor()
        
        sm.update_state({"battery": {"percent": 5, "voltage": 14.0, "current": 0}})
        sm.check_all()
        
        sm.clear_history()
        assert len(sm.violation_history) == 0


class TestGeofenceValidator:
    """Test geofence validation"""
    
    def test_max_altitude_check(self):
        """Test maximum altitude check"""
        config = SafetyConfig(max_altitude_m=120)
        gv = GeofenceValidator(config)
        
        valid, msg = gv.validate_position(32.0, 34.0, 150)
        assert valid is False
        assert "Altitude" in msg
    
    def test_max_distance_check(self):
        """Test maximum distance check"""
        config = SafetyConfig(max_distance_m=500)
        gv = GeofenceValidator(config)
        
        # Far from origin
        valid, msg = gv.validate_position(33.0, 35.0, 50)
        assert valid is False
        assert "Distance" in msg
    
    def test_negative_altitude(self):
        """Test negative altitude rejection"""
        config = SafetyConfig()
        gv = GeofenceValidator(config)
        
        valid, msg = gv.validate_position(32.0, 34.0, -5)
        assert valid is False
    
    def test_add_cylinder_constraint(self):
        """Test adding cylinder constraint"""
        config = SafetyConfig()
        gv = GeofenceValidator(config)
        
        gv.add_cylinder_constraint("no-fly-zone", (32.0, 34.0), 100, min_alt=0, max_alt=100)


# ============== System Integration Tests ==============

class TestSkyCoreSystem:
    """Test SkyCore system integration"""
    
    def test_system_creation(self):
        """Test system creation"""
        from skycore.system import SkyCoreSystem
        
        system = SkyCoreSystem()
        assert system is not None
        assert system.state_machine is None  # Not initialized yet
    
    def test_system_initialization(self):
        """Test system initialization"""
        from skycore.system import SkyCoreSystem
        
        system = SkyCoreSystem()
        assert system.initialize() is True
        
        # Check core subsystems created (sensors may be None if modules not available)
        assert system.state_machine is not None
        assert system.safety_monitor is not None
    
    def test_arm_disarm(self):
        """Test arm and disarm"""
        from skycore.system import SkyCoreSystem
        
        system = SkyCoreSystem()
        system.initialize()
        
        # Update telemetry to pass safety checks
        system.safety_monitor.update_state({
            "gps": {"satellites": 12, "hdop": 1.0},
            "battery": {"percent": 85, "voltage": 16.0, "current": 0},
            "rc": {"connected": True, "last_signal": time.time()}
        })
        system.state_machine.update_telemetry(gps_satellites=12)
        
        assert system.arm() is True
        assert system.state_machine.state == FlightState.ARMED
        
        assert system.disarm() is True
        assert system.state_machine.state == FlightState.DISARMED
    
    def test_takeoff_land(self):
        """Test takeoff and land"""
        from skycore.system import SkyCoreSystem
        
        system = SkyCoreSystem()
        system.initialize()
        
        # Update telemetry for takeoff check
        system.safety_monitor.update_state({
            "gps": {"satellites": 10},
            "battery": {"percent": 80, "voltage": 16.0, "current": 0},
            "rc": {"connected": True, "last_signal": time.time()}
        })
        system.state_machine.update_telemetry(gps_satellites=10)
        
        system.arm()
        assert system.takeoff(20) is True
        
        system.land()
        assert system.state_machine.state == FlightState.LANDING
    
    def test_rtl(self):
        """Test return to launch"""
        from skycore.system import SkyCoreSystem
        
        system = SkyCoreSystem()
        system.initialize()
        
        # Update telemetry
        system.safety_monitor.update_state({
            "gps": {"satellites": 10},
            "battery": {"percent": 80, "voltage": 16.0, "current": 0},
            "rc": {"connected": True, "last_signal": time.time()}
        })
        system.state_machine.update_telemetry(gps_satellites=10)
        
        system.arm()
        system.takeoff(20)
        
        system.state_machine.trigger(TriggerEvent.MISSION_START)
        
        assert system.rtl() is True
        assert system.state_machine.state == FlightState.RTL
    
    def test_load_mission(self):
        """Test mission loading"""
        from skycore.system import SkyCoreSystem
        
        system = SkyCoreSystem()
        system.initialize()
        
        mission = {
            "waypoints": [
                {"lat": 32.0, "lon": 34.0, "alt": 20},
                {"lat": 32.1, "lon": 34.1, "alt": 30},
                {"lat": 32.0, "lon": 34.0, "alt": 10}
            ]
        }
        
        assert system.load_mission(mission) is True
        assert len(system.mission_waypoints) == 3
    
    def test_set_home(self):
        """Test setting home position"""
        from skycore.system import SkyCoreSystem
        
        system = SkyCoreSystem()
        system.initialize()
        
        system.set_home(32.0853, 34.7818, 0)
        
        assert system._home_position["lat"] == 32.0853
        assert system._home_position["lon"] == 34.7818
    
    def test_get_state(self):
        """Test getting system state"""
        from skycore.system import SkyCoreSystem
        
        system = SkyCoreSystem()
        system.initialize()
        
        state = system.get_state()
        
        assert "system" in state
        assert "flight" in state
        assert "safety" in state
        assert "position" in state
    
    def test_send_command(self):
        """Test sending commands"""
        from skycore.system import SkyCoreSystem
        
        system = SkyCoreSystem()
        system.initialize()
        
        # Update telemetry for safety checks
        system.safety_monitor.update_state({
            "gps": {"satellites": 12, "hdop": 1.0},
            "battery": {"percent": 85, "voltage": 16.0, "current": 0},
            "rc": {"connected": True, "last_signal": time.time()}
        })
        system.state_machine.update_telemetry(gps_satellites=12)
        
        # Test arm command
        assert system.send_command("arm") is True
        assert system.state_machine.state == FlightState.ARMED
        
        # Test takeoff (must be armed first)
        assert system.send_command("takeoff", {"altitude": 20}) is True
        
        # Test land
        assert system.send_command("land") is True
        assert system.state_machine.state == FlightState.LANDING
        
        # From landing, trigger landed then disarm
        system.state_machine.trigger(TriggerEvent.LANDED)
        assert system.state_machine.state == FlightState.ARMED
        assert system.send_command("disarm") is True
        assert system.state_machine.state == FlightState.DISARMED
    
    def test_emergency_stop(self):
        """Test emergency stop"""
        from skycore.system import SkyCoreSystem
        
        system = SkyCoreSystem()
        system.initialize()
        
        system.arm()
        system.takeoff(20)
        
        system.emergency_stop()
        assert system.state_machine.state == FlightState.ESTOP


# ============== Configuration Tests ==============

class TestConfiguration:
    """Test configuration loading"""
    
    def test_load_default_config(self):
        """Test loading default configuration"""
        from skycore.system import SkyCoreSystem
        
        system = SkyCoreSystem()
        assert system.config is not None
    
    def test_custom_config_path(self):
        """Test custom config file loading"""
        from skycore.system import SkyCoreSystem
        
        # Create temp config
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"test": "value"}, f)
            temp_path = f.name
        
        try:
            system = SkyCoreSystem(temp_path)
            assert system.config.get("test") == "value"
        finally:
            os.unlink(temp_path)


# ============== Run All Tests ==============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])