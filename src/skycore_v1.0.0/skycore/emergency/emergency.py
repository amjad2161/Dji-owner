"""
SkyCore Emergency Handler
=========================
Emergency procedures and failsafe management for drone operations.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

log = logging.getLogger(__name__)


class EmergencyType(Enum):
    """Emergency situation types."""
    LOW_BATTERY = "low_battery"
    GPS_LOSS = "gps_loss"
    RC_LOSS = "rc_loss"
    LINK_LOSS = "link_loss"
    GEOMAGNETIC_ERROR = "geomagnetic_error"
    IMU_ERROR = "imu_error"
    BAROMETER_ERROR = "barometer_error"
    WIND_OVERSPEED = "wind_overspeed"
    GEOMAGNETIC_COMPASS_ERROR = "compass_error"
    OBSTACLE_DETECTED = "obstacle_detected"
    SENSOR_FAILURE = "sensor_failure"
    EMERGENCY_LAND = "emergency_land"
    KILL_SWITCH = "kill_switch"
    FLYAWAY = "flyaway"
    UNKNOWN = "unknown"


class EmergencyAction(Enum):
    """Emergency response actions."""
    HOVER = "hover"
    LAND = "land"
    RETURN_HOME = "return_home"
    DESCEND = "descend"
    CLIMB = "climb"
    STOP_MOTORS = "stop_motors"
    EMERGENCY_LAND = "emergency_land"
    CONTINUE = "continue"


@dataclass
class EmergencyState:
    """Current emergency state."""
    emergency_type: EmergencyType
    severity: int  # 1-5, 5 being most severe
    timestamp: float
    description: str
    active: bool = True
    acknowledged: bool = False
    auto_resolved: bool = False
    resolution_time: Optional[float] = None
    drone_state: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'type': self.emergency_type.value,
            'severity': self.severity,
            'timestamp': self.timestamp,
            'description': self.description,
            'active': self.active,
            'acknowledged': self.acknowledged,
            'auto_resolved': self.auto_resolved,
            'duration_sec': time.time() - self.timestamp if self.active else 0,
            'drone_state': self.drone_state
        }


@dataclass
class EmergencyConfig:
    """Emergency handler configuration."""
    low_battery_threshold: float = 20.0  # percent
    critical_battery_threshold: float = 10.0  # percent
    rth_battery_threshold: float = 30.0  # percent
    gps_min_sats: int = 6
    link_loss_timeout: float = 5.0  # seconds
    rc_loss_timeout: float = 3.0  # seconds
    max_wind_speed: float = 40.0  # km/h
    max_altitude: float = 120.0  # meters
    min_altitude: float = 2.0  # meters
    home_distance_max: float = 5000.0  # meters
    geofence_margin: float = 50.0  # meters


class EmergencyHandler:
    """
    Emergency procedures and failsafe handler.
    
    Manages all emergency scenarios including:
    - Low battery procedures
    - GPS/sensor failures
    - Communication loss
    - Geofence violations
    - Obstacle detection
    - Manual emergency stops
    
    Features:
    - Multi-level severity system
    - Automatic and manual responses
    - Recovery procedures
    - Emergency logging
    """
    
    def __init__(self, config: Optional[EmergencyConfig] = None):
        """
        Initialize emergency handler.
        
        Args:
            config: Emergency configuration
        """
        self.config = config or EmergencyConfig()
        
        # Current state
        self.current_emergency: Optional[EmergencyState] = None
        self.emergency_history: deque = deque(maxlen=100)
        
        # Callbacks
        self._emergency_callbacks: Dict[EmergencyType, List[Callable]] = {}
        self._all_emergency_callbacks: List[Callable] = []
        self._recovery_callbacks: List[Callable] = []
        
        # Monitoring state
        self.battery_history: deque = deque(maxlen=60)
        self.link_quality_history: deque = deque(maxlen=30)
        self.last_valid_telemetry: float = 0
        self.rth_triggered: bool = False
        
        # Statistics
        self.total_emergencies = 0
        self.total_recoveries = 0
        self.last_emergency_time: Optional[float] = None
        
        log.info("Emergency handler initialized")
    
    async def handle_telemetry(self, telemetry: Dict):
        """
        Process telemetry and check for emergency conditions.
        
        Args:
            telemetry: Drone telemetry dictionary
        """
        self.last_valid_telemetry = time.time()
        
        # Check each emergency condition
        await self._check_battery(telemetry)
        await self._check_gps(telemetry)
        await self._check_link(telemetry)
        await self._check_sensors(telemetry)
        await self._check_wind(telemetry)
        await self._check_geofence(telemetry)
        await self._check_altitude(telemetry)
    
    async def _check_battery(self, telemetry: Dict):
        """Check battery emergency conditions."""
        battery = telemetry.get('battery_percent', 100)
        voltage = telemetry.get('battery_voltage', 0)
        
        self.battery_history.append({'time': time.time(), 'battery': battery})
        
        # Critical battery
        if battery <= self.config.critical_battery_threshold:
            await self._trigger_emergency(
                EmergencyType.LOW_BATTERY,
                severity=5,
                description=f"Critical battery: {battery:.1f}%",
                drone_state=telemetry
            )
        
        # Low battery - suggest RTH
        elif battery <= self.config.low_battery_threshold:
            await self._trigger_emergency(
                EmergencyType.LOW_BATTERY,
                severity=3,
                description=f"Low battery: {battery:.1f}%",
                drone_state=telemetry
            )
        
        # RTH threshold
        elif battery <= self.config.rth_battery_threshold and not self.rth_triggered:
            await self._trigger_emergency(
                EmergencyType.LOW_BATTERY,
                severity=2,
                description=f"Battery low, recommend RTH: {battery:.1f}%",
                drone_state=telemetry
            )
    
    async def _check_gps(self, telemetry: Dict):
        """Check GPS emergency conditions."""
        gps_sats = telemetry.get('gps_satellites', 0)
        gps_fix = telemetry.get('gps_fix', False)
        
        # GPS failure
        if gps_sats < self.config.gps_min_sats and gps_fix == False:
            await self._trigger_emergency(
                EmergencyType.GPS_LOSS,
                severity=4,
                description=f"GPS lost: {gps_sats} satellites",
                drone_state=telemetry
            )
        
        # Weak GPS
        elif gps_sats < self.config.gps_min_sats:
            log.warning(f"Weak GPS: {gps_sats} satellites")
    
    async def _check_link(self, telemetry: Dict):
        """Check communication link status."""
        link_quality = telemetry.get('link_quality', 100)
        
        self.link_quality_history.append({'time': time.time(), 'quality': link_quality})
        
        # Link loss
        time_since_telemetry = time.time() - self.last_valid_telemetry
        
        if time_since_telemetry > self.config.link_loss_timeout:
            await self._trigger_emergency(
                EmergencyType.LINK_LOSS,
                severity=4,
                description=f"Link lost for {time_since_telemetry:.1f}s",
                drone_state=telemetry
            )
        
        # Weak link
        elif link_quality < 50:
            log.warning(f"Weak link quality: {link_quality}%")
    
    async def _check_sensors(self, telemetry: Dict):
        """Check sensor health."""
        compass_error = telemetry.get('compass_error', False)
        imu_error = telemetry.get('imu_error', False)
        baro_error = telemetry.get('barometer_error', False)
        
        if compass_error:
            await self._trigger_emergency(
                EmergencyType.GEOMAGNETIC_ERROR,
                severity=4,
                description="Compass error detected",
                drone_state=telemetry
            )
        
        if imu_error:
            await self._trigger_emergency(
                EmergencyType.IMU_ERROR,
                severity=5,
                description="IMU error - immediate land recommended",
                drone_state=telemetry
            )
        
        if baro_error:
            await self._trigger_emergency(
                EmergencyType.BAROMETER_ERROR,
                severity=3,
                description="Barometer error",
                drone_state=telemetry
            )
    
    async def _check_wind(self, telemetry: Dict):
        """Check wind conditions."""
        wind_speed = telemetry.get('wind_speed', 0)  # km/h
        
        if wind_speed > self.config.max_wind_speed:
            await self._trigger_emergency(
                EmergencyType.WIND_OVERSPEED,
                severity=3,
                description=f"Wind overspeed: {wind_speed} km/h",
                drone_state=telemetry
            )
    
    async def _check_geofence(self, telemetry: Dict):
        """Check geofence violations."""
        in_geofence = telemetry.get('in_geofence', True)
        distance_to_home = telemetry.get('distance_to_home', 0)
        
        if not in_geofence:
            await self._trigger_emergency(
                EmergencyType.UNKNOWN,  # Could be geofence specific type
                severity=4,
                description="Geofence violation",
                drone_state=telemetry
            )
        
        if distance_to_home > self.config.home_distance_max:
            log.warning(f"Distance from home exceeds limit: {distance_to_home}m")
    
    async def _check_altitude(self, telemetry: Dict):
        """Check altitude limits."""
        altitude = telemetry.get('altitude', 0)
        
        if altitude > self.config.max_altitude:
            await self._trigger_emergency(
                EmergencyType.UNKNOWN,
                severity=3,
                description=f"Altitude exceeded: {altitude}m",
                drone_state=telemetry
            )
        
        if altitude < self.config.min_altitude:
            log.warning(f"Low altitude: {altitude}m")
    
    async def _trigger_emergency(self, emergency_type: EmergencyType, severity: int,
                                description: str, drone_state: Dict):
        """Trigger an emergency state."""
        # Check if already handling same emergency
        if self.current_emergency and self.current_emergency.active:
            if self.current_emergency.emergency_type == emergency_type:
                return  # Already handling this
        
        state = EmergencyState(
            emergency_type=emergency_type,
            severity=severity,
            timestamp=time.time(),
            description=description,
            drone_state=drone_state
        )
        
        self.current_emergency = state
        self.total_emergencies += 1
        self.last_emergency_time = time.time()
        
        log.warning(f"EMERGENCY: {emergency_type.value} (severity {severity}) - {description}")
        
        # Call emergency callbacks
        for callback in self._all_emergency_callbacks:
            try:
                await callback(state)
            except Exception as e:
                log.error(f"Emergency callback error: {e}")
        
        if emergency_type in self._emergency_callbacks:
            for callback in self._emergency_callbacks[emergency_type]:
                try:
                    await callback(state)
                except Exception as e:
                    log.error(f"Emergency callback error: {e}")
    
    async def acknowledge(self):
        """Acknowledge current emergency."""
        if self.current_emergency:
            self.current_emergency.acknowledged = True
            log.info(f"Emergency acknowledged: {self.current_emergency.emergency_type.value}")
    
    async def resolve(self, auto: bool = False):
        """Resolve current emergency."""
        if self.current_emergency:
            self.current_emergency.active = False
            self.current_emergency.auto_resolved = auto
            self.current_emergency.resolution_time = time.time()
            
            log.info(f"Emergency resolved (auto={auto}): {self.current_emergency.emergency_type.value}")
            
            # Add to history
            self.emergency_history.append(self.current_emergency)
            
            # Call recovery callbacks
            for callback in self._recovery_callbacks:
                try:
                    await callback(self.current_emergency)
                except Exception as e:
                    log.error(f"Recovery callback error: {e}")
            
            self.total_recoveries += 1
            self.current_emergency = None
    
    def get_action(self) -> EmergencyAction:
        """Get recommended emergency action."""
        if not self.current_emergency:
            return EmergencyAction.CONTINUE
        
        emergency = self.current_emergency
        
        # Determine action based on emergency type and severity
        if emergency.severity >= 5:
            return EmergencyAction.EMERGENCY_LAND
        elif emergency.emergency_type == EmergencyType.LOW_BATTERY:
            if emergency.severity >= 4:
                return EmergencyAction.RETURN_HOME
            else:
                return EmergencyAction.DESCEND
        elif emergency.emergency_type in [EmergencyType.GPS_LOSS, EmergencyType.LINK_LOSS]:
            return EmergencyAction.RETURN_HOME
        elif emergency.emergency_type == EmergencyType.IMU_ERROR:
            return EmergencyAction.EMERGENCY_LAND
        else:
            return EmergencyAction.HOVER
    
    def on_emergency(self, callback: Callable):
        """Register callback for all emergencies."""
        self._all_emergency_callbacks.append(callback)
    
    def on_emergency_type(self, emergency_type: EmergencyType, callback: Callable):
        """Register callback for specific emergency type."""
        if emergency_type not in self._emergency_callbacks:
            self._emergency_callbacks[emergency_type] = []
        self._emergency_callbacks[emergency_type].append(callback)
    
    def on_recovery(self, callback: Callable):
        """Register recovery callback."""
        self._recovery_callbacks.append(callback)
    
    def get_current_state(self) -> Optional[EmergencyState]:
        """Get current emergency state."""
        return self.current_emergency
    
    def get_history(self) -> List[EmergencyState]:
        """Get emergency history."""
        return list(self.emergency_history)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get handler statistics."""
        return {
            'total_emergencies': self.total_emergencies,
            'total_recoveries': self.total_recoveries,
            'current_emergency': self.current_emergency.to_dict() if self.current_emergency else None,
            'last_emergency_time': self.last_emergency_time,
            'rth_triggered': self.rth_triggered,
            'avg_battery': sum(h['battery'] for h in self.battery_history) / max(1, len(self.battery_history))
        }


class FailsafeManager:
    """Manage failsafe triggers and recovery procedures."""
    
    def __init__(self, emergency_handler: EmergencyHandler):
        self.emergency_handler = emergency_handler
    
    async def execute_failsafe(self, action: EmergencyAction, drone) -> bool:
        """Execute failsafe action."""
        try:
            if action == EmergencyAction.RETURN_HOME:
                await drone.return_to_home()
                self.emergency_handler.rth_triggered = True
                log.info("Failsafe: Return to home executed")
                return True
            elif action == EmergencyAction.EMERGENCY_LAND:
                await drone.emergency_land()
                log.info("Failsafe: Emergency land executed")
                return True
            elif action == EmergencyAction.LAND:
                await drone.land()
                log.info("Failsafe: Land executed")
                return True
            elif action == EmergencyAction.HOVER:
                await drone.set_velocity(0, 0, 0)
                log.info("Failsafe: Hover executed")
                return True
            else:
                return False
        except Exception as e:
            log.error(f"Failsafe execution error: {e}")
            return False


# Export
__all__ = ['EmergencyHandler', 'EmergencyType', 'EmergencyAction', 'EmergencyState', 'EmergencyConfig', 'FailsafeManager']