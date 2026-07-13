"""
Unit Tests for SkyCore Core Modules

Tests:
- drone.py (abstract interface)
- safety.py (SafeDrone wrapper)
- mavlink.py (MAVLink backend)
- types.py (GeoPoint, Telemetry, etc.)
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import modules under test
import sys
sys.path.insert(0, "C:/Users/Mobar/Downloads/drone flycore/package/user_input_files")

from skycore.core.drone import Drone
from skycore.core.types import GeoPoint, Telemetry, FlightMode, GeofenceConfig


class TestGeoPoint:
    """Tests for GeoPoint class."""
    
    def test_constructor(self):
        p = GeoPoint(32.0855, 34.7820, 50.0)
        assert p.lat == 32.0855
        assert p.lon == 34.7820
        assert p.alt == 50.0
    
    def test_haversine_m(self):
        p1 = GeoPoint(32.0855, 34.7820, 50.0)
        p2 = GeoPoint(32.0955, 34.7920, 50.0)  # ~1.5km away
        dist = p1.haversine_m(p2)
        assert 1400 < dist < 1600  # Approximately 1.5km
    
    def test_haversine_m_same_point(self):
        p = GeoPoint(32.0855, 34.7820, 50.0)
        assert p.haversine_m(p) == 0.0
    
    def test_to_dict(self):
        p = GeoPoint(32.0855, 34.7820, 50.0)
        d = p.to_dict()
        assert d["lat"] == 32.0855
        assert d["lon"] == 34.7820
        assert d["alt"] == 50.0
    
    def test_from_dict(self):
        d = {"lat": 32.0855, "lon": 34.7820, "alt": 50.0}
        p = GeoPoint.from_dict(d)
        assert p.lat == 32.0855
        assert p.lon == 34.7820
        assert p.alt == 50.0
    
    def test_validation(self):
        # Invalid latitude
        with pytest.raises(ValueError):
            GeoPoint(91.0, 0.0, 0.0)
        
        # Invalid longitude
        with pytest.raises(ValueError):
            GeoPoint(0.0, 181.0, 0.0)


class TestTelemetry:
    """Tests for Telemetry class."""
    
    def test_constructor(self):
        tm = Telemetry(
            timestamp=datetime.utcnow(),
            position=GeoPoint(32.0855, 34.7820, 50.0),
            velocity_xyz=(5.0, 0.0, 0.0),
            yaw_deg=90.0,
            pitch_deg=0.0,
            roll_deg=0.0,
            battery_percent=85.0,
            battery_voltage=15.2,
            gps_satellites=15,
            gimbal_pitch_deg=-45.0,
            flight_mode=FlightMode.MISSION,
            home=GeoPoint(32.0855, 34.7820, 0.0),
        )
        assert tm.battery_percent == 85.0
        assert tm.gps_satellites == 15
        assert tm.flight_mode == FlightMode.MISSION
    
    def test_to_dict(self):
        tm = Telemetry(
            timestamp=datetime.utcnow(),
            position=GeoPoint(32.0855, 34.7820, 50.0),
            velocity_xyz=(5.0, 0.0, 0.0),
            yaw_deg=90.0,
            pitch_deg=0.0,
            roll_deg=0.0,
            battery_percent=85.0,
            battery_voltage=15.2,
            gps_satellites=15,
            gimbal_pitch_deg=-45.0,
            flight_mode=FlightMode.MISSION,
        )
        d = tm.to_dict()
        assert d["battery_percent"] == 85.0
        assert d["gps_satellites"] == 15


class TestGeofenceConfig:
    """Tests for GeofenceConfig."""
    
    def test_constructor_defaults(self):
        cfg = GeofenceConfig(
            home=GeoPoint(32.0855, 34.7820, 0.0),
            max_altitude_m=120.0,
            max_distance_m=5000.0,
        )
        assert cfg.max_altitude_m == 120.0
        assert cfg.max_distance_m == 5000.0


class MockDrone(Drone):
    """Mock drone for testing."""
    
    name = "mock"
    
    def __init__(self):
        self._connected = True
        self._telemetry = Telemetry(
            timestamp=datetime.utcnow(),
            position=GeoPoint(32.0855, 34.7820, 50.0),
            velocity_xyz=(0.0, 0.0, 0.0),
            yaw_deg=0.0,
            pitch_deg=0.0,
            roll_deg=0.0,
            battery_percent=80.0,
            battery_voltage=15.0,
            gps_satellites=12,
            gimbal_pitch_deg=0.0,
            flight_mode=FlightMode.MISSION,
        )
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    async def connect(self):
        self._connected = True
    
    async def disconnect(self):
        self._connected = False
    
    async def takeoff(self, altitude_m: float = 5.0):
        pass
    
    async def land(self):
        pass
    
    async def return_to_home(self):
        pass
    
    async def goto(self, point: GeoPoint, speed_mps: float = 5.0):
        pass
    
    async def set_velocity(self, vx: float, vy: float, vz: float, yaw_rate: float = 0.0):
        pass
    
    async def set_yaw(self, yaw_deg: float):
        pass
    
    async def set_gimbal(self, pitch_deg: float):
        pass
    
    async def take_photo(self) -> str:
        return "mock://photo"
    
    async def start_recording(self):
        pass
    
    async def stop_recording(self):
        pass
    
    async def get_telemetry(self) -> Telemetry:
        return self._telemetry
    
    def telemetry_stream(self):
        async def gen():
            while True:
                yield self._telemetry
                await asyncio.sleep(0.1)
        return gen()
    
    async def __aenter__(self):
        self._connected = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._connected = False


@pytest.mark.asyncio
class TestSafeDrone:
    """Tests for SafeDrone wrapper."""
    
    async def test_takeoff_geofence_check(self):
        from safety import SafeDrone
        
        mock = MockDrone()
        cfg = GeofenceConfig(
            home=GeoPoint(32.0855, 34.7820, 0.0),
            max_altitude_m=100.0,
            max_distance_m=5000.0,
        )
        
        safe = SafeDrone(mock, cfg)
        await safe.connect()
        
        # This should pass
        await safe.takeoff(50.0)
        
        # This should raise SafetyError
        from safety import SafetyError
        with pytest.raises(SafetyError):
            await safe.takeoff(150.0)  # Exceeds geofence
        
        await safe.disconnect()
    
    async def test_goto_geofence_check(self):
        from safety import SafeDrone
        
        mock = MockDrone()
        cfg = GeofenceConfig(
            home=GeoPoint(32.0855, 34.7820, 0.0),
            max_altitude_m=100.0,
            max_distance_m=10000.0,  # 10km
        )
        
        safe = SafeDrone(mock, cfg)
        await safe.connect()
        
        # Far point (would exceed radius)
        far_point = GeoPoint(32.1855, 34.8820, 50.0)  # ~15km away
        
        from safety import SafetyError
        with pytest.raises(SafetyError):
            await safe.goto(far_point, 5.0)
        
        await safe.disconnect()
    
    async def test_halt_on_low_gps(self):
        from safety import SafeDrone
        
        mock = MockDrone()
        mock._telemetry = Telemetry(
            timestamp=datetime.utcnow(),
            position=GeoPoint(32.0855, 34.7820, 50.0),
            velocity_xyz=(0.0, 0.0, 0.0),
            yaw_deg=0.0,
            pitch_deg=0.0,
            roll_deg=0.0,
            battery_percent=80.0,
            battery_voltage=15.0,
            gps_satellites=5,  # Below minimum of 8
            gimbal_pitch_deg=0.0,
            flight_mode=FlightMode.MISSION,
        )
        
        cfg = GeofenceConfig(
            home=GeoPoint(32.0855, 34.7820, 0.0),
            max_altitude_m=100.0,
            max_distance_m=10000.0,
            min_gps_satellites=8,
        )
        
        safe = SafeDrone(mock, cfg)
        await safe.connect()
        
        # Start the monitor loop to detect GPS issue
        safe._monitor_task = asyncio.create_task(safe._monitor())
        await asyncio.sleep(0.1)  # Let monitor detect low GPS
        
        # Should block velocity command when GPS is low
        from safety import SafetyError
        with pytest.raises(SafetyError):
            await safe.set_velocity(5.0, 0.0, 0.0, 0.0)
        
        safe._monitor_task.cancel()
        await safe.disconnect()


class TestDroneInterface:
    """Tests for Drone abstract interface."""
    
    def test_abstract_methods(self):
        """Verify Drone is properly abstract."""
        with pytest.raises(TypeError):
            Drone()  # Cannot instantiate abstract class
    
    def test_interface_compliance(self):
        """Verify MockDrone implements all required methods."""
        mock = MockDrone()
        
        # All abstract methods should exist
        assert hasattr(mock, 'connect')
        assert hasattr(mock, 'disconnect')
        assert hasattr(mock, 'takeoff')
        assert hasattr(mock, 'land')
        assert hasattr(mock, 'return_to_home')
        assert hasattr(mock, 'goto')
        assert hasattr(mock, 'set_velocity')
        assert hasattr(mock, 'set_yaw')
        assert hasattr(mock, 'set_gimbal')
        assert hasattr(mock, 'take_photo')
        assert hasattr(mock, 'start_recording')
        assert hasattr(mock, 'stop_recording')
        assert hasattr(mock, 'get_telemetry')
        assert hasattr(mock, 'telemetry_stream')
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager protocol."""
        mock = MockDrone()
        
        async with mock as drone:
            assert drone.is_connected
        
        # After exiting context, should be disconnected
        # (land is called automatically, then disconnect)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])