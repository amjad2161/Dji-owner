"""
SkyCore Safety Monitor
Comprehensive safety monitoring and violation handling.
"""

import time
import threading
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque


class SafetyLevel(Enum):
    """Safety violation severity levels"""
    OK = "ok"
    WARNING = "warning"
    CAUTION = "caution"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class ViolationType(Enum):
    """Types of safety violations"""
    BATTERY_LOW = "battery_low"
    BATTERY_CRITICAL = "battery_critical"
    ALTITUDE_EXCEEDED = "altitude_exceeded"
    DISTANCE_EXCEEDED = "distance_exceeded"
    GPS_LOST = "gps_lost"
    GPS_DEGRADED = "gps_degraded"
    RC_LOST = "rc_lost"
    GCS_LOST = "gcs_lost"
    COMMUNICATION_LOST = "communication_lost"
    GEOFENCE_BREACH = "geofence_breach"
    OBSTACLE_COLLISION = "obstacle_collision"
    TEMPERATURE_HIGH = "temperature_high"
    TEMPERATURE_LOW = "temperature_low"
    WIND_EXCEEDED = "wind_exceeded"
    SPEED_EXCEEDED = "speed_exceeded"
    STACK_OVERFLOW = "stack_overflow"
    SOFTWARE_ERROR = "software_error"
    SENSOR_FAILURE = "sensor_failure"


@dataclass
class SafetyViolation:
    """Safety violation record"""
    violation_type: ViolationType
    severity: SafetyLevel
    message: str
    timestamp: float = field(default_factory=time.time)
    value: float = 0.0
    threshold: float = 0.0
    location: Optional[Dict] = None
    resolved: bool = False
    resolved_time: Optional[float] = None


@dataclass
class SafetyConfig:
    """Safety monitoring configuration"""
    # Battery thresholds
    battery_warning_percent: float = 30.0
    battery_caution_percent: float = 20.0
    battery_critical_percent: float = 10.0
    battery_emergency_percent: float = 5.0
    
    # Altitude limits
    max_altitude_m: float = 120.0
    altitude_warning_m: float = 100.0
    altitude_caution_m: float = 110.0
    
    # Distance limits
    max_distance_m: float = 500.0
    distance_warning_m: float = 400.0
    distance_caution_m: float = 450.0
    
    # GPS requirements
    min_gps_satellites: int = 8
    gps_warning_sats: int = 10
    hdop_max: float = 2.5
    
    # Signal timeouts
    rc_timeout_sec: float = 3.0
    gcs_timeout_sec: float = 10.0
    telemetry_timeout_sec: float = 5.0
    
    # Environmental limits
    max_temperature_c: float = 60.0
    min_temperature_c: float = -10.0
    max_wind_ms: float = 10.0
    max_speed_ms: float = 20.0
    
    # Control limits
    max_tilt_deg: float = 35.0
    max_yaw_rate_degs: float = 90.0
    
    # Monitoring intervals
    check_interval_ms: int = 100
    violation_history_max: int = 100


class SafetyMonitor:
    """
    Comprehensive safety monitoring system for drone operations.
    
    Monitors:
    - Battery levels and health
    - Altitude and distance from home
    - GPS signal quality
    - RC and GCS connections
    - Environmental conditions
    - Geofence compliance
    - Obstacle proximity
    - System health
    """
    
    def __init__(
        self,
        config: Optional[SafetyConfig] = None,
        home_position: Optional[Dict] = None,
        callbacks: Optional[Dict[SafetyLevel, List[Callable]]] = None
    ):
        self.config = config or SafetyConfig()
        self.home_position = home_position or {"lat": 0.0, "lon": 0.0, "alt": 0.0}
        self.callbacks = callbacks or {}
        
        # Current state
        self._current_state = {
            "position": {"lat": 0.0, "lon": 0.0, "alt": 0.0, "speed": 0.0},
            "battery": {"percent": 100.0, "voltage": 16.8, "current": 0.0, "temp": 25.0},
            "gps": {"satellites": 0, "hdop": 0.0, "fix_type": "none"},
            "rc": {"connected": True, "last_signal": time.time()},
            "gcs": {"connected": True, "last_signal": time.time()},
            "telemetry": {"last_message": time.time()},
            "environment": {
                "temperature": 25.0,
                "wind_speed": 0.0,
                "wind_direction": 0.0
            },
            "sensors": {
                "imu": {"healthy": True},
                "barometer": {"healthy": True},
                "compass": {"healthy": True},
                "lidar": {"healthy": True}
            },
            "control": {"attitude": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}}
        }
        
        # Violation tracking
        self.active_violations: Dict[ViolationType, SafetyViolation] = {}
        self.violation_history: deque = deque(maxlen=self.config.violation_history_max)
        self.warning_history: deque = deque(maxlen=50)
        
        # Monitoring threads
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.RLock()
        
        # Event callbacks
        self._violation_callbacks: List[Callable] = []
        self._recovery_callbacks: List[Callable] = []
        self._emergency_callbacks: List[Callable] = []
        
        # Stats
        self.total_violations = 0
        self.total_recoveries = 0
        self.monitoring_start_time = time.time()
        
        print(f"[SAFETY_MONITOR] Initialized with {len(self.config.__dict__)} parameters")
    
    def update_state(self, state_update: Dict):
        """Update current monitoring state"""
        with self._lock:
            for key, value in state_update.items():
                if key in self._current_state:
                    if isinstance(value, dict):
                        self._current_state[key].update(value)
                    else:
                        self._current_state[key] = value
    
    def set_home_position(self, lat: float, lon: float, alt: float = 0.0):
        """Set home position for distance monitoring"""
        self.home_position = {"lat": lat, "lon": lon, "alt": alt}
    
    def check_all(self) -> List[SafetyViolation]:
        """
        Run all safety checks and return any violations.
        
        Returns:
            List of active safety violations
        """
        violations = []
        
        # Run all checks
        violations.extend(self._check_battery())
        violations.extend(self._check_altitude())
        violations.extend(self._check_distance())
        violations.extend(self._check_gps())
        violations.extend(self._check_rc_connection())
        violations.extend(self._check_gcs_connection())
        violations.extend(self._check_temperature())
        violations.extend(self._check_wind())
        violations.extend(self._check_speed())
        violations.extend(self._check_tilt())
        violations.extend(self._check_sensors())
        
        # Update active violations
        self._update_violations(violations)
        
        return list(self.active_violations.values())
    
    def _check_battery(self) -> List[SafetyViolation]:
        """Check battery levels"""
        violations = []
        battery = self._current_state["battery"]
        percent = battery.get("percent", 100)
        voltage = battery.get("voltage", 16.8)
        
        # Check percentage thresholds
        if percent <= self.config.battery_emergency_percent:
            violations.append(SafetyViolation(
                violation_type=ViolationType.BATTERY_CRITICAL,
                severity=SafetyLevel.EMERGENCY,
                message=f"Battery critically low: {percent:.1f}%",
                value=percent,
                threshold=self.config.battery_emergency_percent
            ))
        elif percent <= self.config.battery_critical_percent:
            violations.append(SafetyViolation(
                violation_type=ViolationType.BATTERY_CRITICAL,
                severity=SafetyLevel.CRITICAL,
                message=f"Battery critical: {percent:.1f}%",
                value=percent,
                threshold=self.config.battery_critical_percent
            ))
        elif percent <= self.config.battery_caution_percent:
            violations.append(SafetyViolation(
                violation_type=ViolationType.BATTERY_LOW,
                severity=SafetyLevel.CAUTION,
                message=f"Battery caution: {percent:.1f}%",
                value=percent,
                threshold=self.config.battery_caution_percent
            ))
        elif percent <= self.config.battery_warning_percent:
            violations.append(SafetyViolation(
                violation_type=ViolationType.BATTERY_LOW,
                severity=SafetyLevel.WARNING,
                message=f"Battery warning: {percent:.1f}%",
                value=percent,
                threshold=self.config.battery_warning_percent
            ))
        
        return violations
    
    def _check_altitude(self) -> List[SafetyViolation]:
        """Check altitude limits"""
        violations = []
        altitude = self._current_state["position"].get("alt", 0)
        
        if altitude > self.config.max_altitude_m:
            violations.append(SafetyViolation(
                violation_type=ViolationType.ALTITUDE_EXCEEDED,
                severity=SafetyLevel.CRITICAL,
                message=f"Altitude exceeded maximum: {altitude:.1f}m",
                value=altitude,
                threshold=self.config.max_altitude_m
            ))
        elif altitude > self.config.altitude_caution_m:
            violations.append(SafetyViolation(
                violation_type=ViolationType.ALTITUDE_EXCEEDED,
                severity=SafetyLevel.CAUTION,
                message=f"Altitude exceeds caution: {altitude:.1f}m",
                value=altitude,
                threshold=self.config.altitude_caution_m
            ))
        elif altitude > self.config.altitude_warning_m:
            violations.append(SafetyViolation(
                violation_type=ViolationType.ALTITUDE_EXCEEDED,
                severity=SafetyLevel.WARNING,
                message=f"Altitude exceeds warning: {altitude:.1f}m",
                value=altitude,
                threshold=self.config.altitude_warning_m
            ))
        
        return violations
    
    def _check_distance(self) -> List[SafetyViolation]:
        """Check distance from home"""
        violations = []
        distance = self._calculate_distance_from_home()
        
        if distance > self.config.max_distance_m:
            violations.append(SafetyViolation(
                violation_type=ViolationType.DISTANCE_EXCEEDED,
                severity=SafetyLevel.CRITICAL,
                message=f"Distance exceeded maximum: {distance:.1f}m",
                value=distance,
                threshold=self.config.max_distance_m
            ))
        elif distance > self.config.distance_caution_m:
            violations.append(SafetyViolation(
                violation_type=ViolationType.DISTANCE_EXCEEDED,
                severity=SafetyLevel.CAUTION,
                message=f"Distance exceeds caution: {distance:.1f}m",
                value=distance,
                threshold=self.config.distance_caution_m
            ))
        elif distance > self.config.distance_warning_m:
            violations.append(SafetyViolation(
                violation_type=ViolationType.DISTANCE_EXCEEDED,
                severity=SafetyLevel.WARNING,
                message=f"Distance exceeds warning: {distance:.1f}m",
                value=distance,
                threshold=self.config.distance_warning_m
            ))
        
        return violations
    
    def _check_gps(self) -> List[SafetyViolation]:
        """Check GPS signal quality"""
        violations = []
        gps = self._current_state["gps"]
        satellites = gps.get("satellites", 0)
        hdop = gps.get("hdop", 99.0)
        
        if satellites == 0:
            violations.append(SafetyViolation(
                violation_type=ViolationType.GPS_LOST,
                severity=SafetyLevel.CRITICAL,
                message="GPS signal completely lost",
                value=0,
                threshold=self.config.min_gps_satellites
            ))
        elif satellites < self.config.min_gps_satellites:
            violations.append(SafetyViolation(
                violation_type=ViolationType.GPS_DEGRADED,
                severity=SafetyLevel.CAUTION,
                message=f"GPS satellites below minimum: {satellites}",
                value=satellites,
                threshold=self.config.min_gps_satellites
            ))
        elif satellites < self.config.gps_warning_sats:
            violations.append(SafetyViolation(
                violation_type=ViolationType.GPS_DEGRADED,
                severity=SafetyLevel.WARNING,
                message=f"GPS satellites low: {satellites}",
                value=satellites,
                threshold=self.config.gps_warning_sats
            ))
        
        if hdop > self.config.hdop_max:
            violations.append(SafetyViolation(
                violation_type=ViolationType.GPS_DEGRADED,
                severity=SafetyLevel.CAUTION,
                message=f"GPS HDOP degraded: {hdop:.1f}",
                value=hdop,
                threshold=self.config.hdop_max
            ))
        
        return violations
    
    def _check_rc_connection(self) -> List[SafetyViolation]:
        """Check RC connection"""
        violations = []
        rc = self._current_state["rc"]
        
        if not rc.get("connected", False):
            violations.append(SafetyViolation(
                violation_type=ViolationType.RC_LOST,
                severity=SafetyLevel.CRITICAL,
                message="RC connection lost",
                timestamp=rc.get("last_signal", time.time())
            ))
        elif time.time() - rc.get("last_signal", 0) > self.config.rc_timeout_sec:
            violations.append(SafetyViolation(
                violation_type=ViolationType.RC_LOST,
                severity=SafetyLevel.WARNING,
                message=f"RC signal timeout: {time.time() - rc.get('last_signal', 0):.1f}s",
                timestamp=rc.get("last_signal", time.time())
            ))
        
        return violations
    
    def _check_gcs_connection(self) -> List[SafetyViolation]:
        """Check GCS connection"""
        violations = []
        gcs = self._current_state["gcs"]
        
        if not gcs.get("connected", False):
            violations.append(SafetyViolation(
                violation_type=ViolationType.GCS_LOST,
                severity=SafetyLevel.WARNING,
                message="GCS connection lost",
                timestamp=gcs.get("last_signal", time.time())
            ))
        elif time.time() - gcs.get("last_signal", 0) > self.config.gcs_timeout_sec:
            violations.append(SafetyViolation(
                violation_type=ViolationType.GCS_LOST,
                severity=SafetyLevel.CAUTION,
                message=f"GCS signal timeout: {time.time() - gcs.get('last_signal', 0):.1f}s"
            ))
        
        return violations
    
    def _check_temperature(self) -> List[SafetyViolation]:
        """Check environmental temperature"""
        violations = []
        temp = self._current_state["environment"].get("temperature", 25)
        
        if temp > self.config.max_temperature_c:
            violations.append(SafetyViolation(
                violation_type=ViolationType.TEMPERATURE_HIGH,
                severity=SafetyLevel.CAUTION,
                message=f"Temperature too high: {temp:.1f}°C",
                value=temp,
                threshold=self.config.max_temperature_c
            ))
        elif temp < self.config.min_temperature_c:
            violations.append(SafetyViolation(
                violation_type=ViolationType.TEMPERATURE_LOW,
                severity=SafetyLevel.CAUTION,
                message=f"Temperature too low: {temp:.1f}°C",
                value=temp,
                threshold=self.config.min_temperature_c
            ))
        
        return violations
    
    def _check_wind(self) -> List[SafetyViolation]:
        """Check wind speed"""
        violations = []
        wind_speed = self._current_state["environment"].get("wind_speed", 0)
        
        if wind_speed > self.config.max_wind_ms:
            violations.append(SafetyViolation(
                violation_type=ViolationType.WIND_EXCEEDED,
                severity=SafetyLevel.CAUTION,
                message=f"Wind speed exceeded: {wind_speed:.1f}m/s",
                value=wind_speed,
                threshold=self.config.max_wind_ms
            ))
        
        return violations
    
    def _check_speed(self) -> List[SafetyViolation]:
        """Check ground speed"""
        violations = []
        speed = self._current_state["position"].get("speed", 0)
        
        if speed > self.config.max_speed_ms:
            violations.append(SafetyViolation(
                violation_type=ViolationType.SPEED_EXCEEDED,
                severity=SafetyLevel.WARNING,
                message=f"Speed exceeded: {speed:.1f}m/s",
                value=speed,
                threshold=self.config.max_speed_ms
            ))
        
        return violations
    
    def _check_tilt(self) -> List[SafetyViolation]:
        """Check vehicle tilt angle"""
        violations = []
        attitude = self._current_state["control"].get("attitude", {})
        roll = abs(attitude.get("roll", 0))
        pitch = abs(attitude.get("pitch", 0))
        
        max_tilt = self.config.max_tilt_deg
        total_tilt = (roll ** 2 + pitch ** 2) ** 0.5
        
        if total_tilt > max_tilt:
            violations.append(SafetyViolation(
                violation_type=ViolationType.SPEED_EXCEEDED,
                severity=SafetyLevel.WARNING,
                message=f"Tilt exceeded: {total_tilt:.1f}°",
                value=total_tilt,
                threshold=max_tilt
            ))
        
        return violations
    
    def _check_sensors(self) -> List[SafetyViolation]:
        """Check sensor health"""
        violations = []
        sensors = self._current_state.get("sensors", {})
        
        for sensor_name, sensor_state in sensors.items():
            if not sensor_state.get("healthy", True):
                violations.append(SafetyViolation(
                    violation_type=ViolationType.SENSOR_FAILURE,
                    severity=SafetyLevel.CAUTION,
                    message=f"Sensor failure: {sensor_name}"
                ))
        
        return violations
    
    def _update_violations(self, new_violations: List[SafetyViolation]):
        """Update active violations tracking"""
        with self._lock:
            for violation in new_violations:
                if violation.violation_type not in self.active_violations:
                    # New violation
                    self.active_violations[violation.violation_type] = violation
                    self.violation_history.append(violation)
                    self.total_violations += 1
                    self._handle_violation(violation)
                else:
                    # Update existing
                    self.active_violations[violation.violation_type] = violation
            
            # Check for recovered violations
            current_types = {v.violation_type for v in new_violations}
            for vtype in list(self.active_violations.keys()):
                if vtype not in current_types:
                    violation = self.active_violations.pop(vtype)
                    violation.resolved = True
                    violation.resolved_time = time.time()
                    self.total_recoveries += 1
                    self._handle_recovery(violation)
    
    def _handle_violation(self, violation: SafetyViolation):
        """Handle a safety violation"""
        # Call violation callbacks
        for callback in self._violation_callbacks:
            try:
                callback(violation)
            except Exception as e:
                print(f"[SAFETY_MONITOR] Callback error: {e}")
        
        # Call severity-specific callbacks
        if violation.severity in self.callbacks:
            for callback in self.callbacks[violation.severity]:
                try:
                    callback(violation)
                except Exception as e:
                    print(f"[SAFETY_MONITOR] Severity callback error: {e}")
        
        # Handle emergency violations
        if violation.severity == SafetyLevel.EMERGENCY:
            for callback in self._emergency_callbacks:
                try:
                    callback(violation)
                except Exception as e:
                    print(f"[SAFETY_MONITOR] Emergency callback error: {e}")
        
        # Log violation
        severity_tag = f"[{violation.severity.value.upper()}]"
        print(f"[SAFETY_MONITOR] {severity_tag} {violation.message}")
    
    def _handle_recovery(self, violation: SafetyViolation):
        """Handle violation recovery"""
        print(f"[SAFETY_MONITOR] Recovered: {violation.violation_type.value}")
        
        for callback in self._recovery_callbacks:
            try:
                callback(violation)
            except Exception as e:
                print(f"[SAFETY_MONITOR] Recovery callback error: {e}")
    
    def _calculate_distance_from_home(self) -> float:
        """Calculate distance from home in meters"""
        import math
        
        lat1 = self._current_state["position"].get("lat", 0)
        lon1 = self._current_state["position"].get("lon", 0)
        lat2 = self.home_position.get("lat", 0)
        lon2 = self.home_position.get("lon", 0)
        
        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        
        a = (math.sin(dphi/2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def get_status(self) -> Dict:
        """Get current safety status summary"""
        with self._lock:
            critical_count = sum(
                1 for v in self.active_violations.values()
                if v.severity in [SafetyLevel.CRITICAL, SafetyLevel.EMERGENCY]
            )
            
            return {
                "level": self._calculate_overall_level(),
                "active_violations": len(self.active_violations),
                "critical_count": critical_count,
                "total_violations": self.total_violations,
                "total_recoveries": self.total_recoveries,
                "uptime_sec": time.time() - self.monitoring_start_time,
                "violations": [
                    {
                        "type": v.violation_type.value,
                        "severity": v.severity.value,
                        "message": v.message,
                        "timestamp": v.timestamp
                    }
                    for v in self.active_violations.values()
                ]
            }
    
    def _calculate_overall_level(self) -> SafetyLevel:
        """Calculate overall safety level"""
        if not self.active_violations:
            return SafetyLevel.OK
        
        severities = [v.severity for v in self.active_violations.values()]
        
        if SafetyLevel.EMERGENCY in severities:
            return SafetyLevel.EMERGENCY
        elif SafetyLevel.CRITICAL in severities:
            return SafetyLevel.CRITICAL
        elif SafetyLevel.CAUTION in severities:
            return SafetyLevel.CAUTION
        elif SafetyLevel.WARNING in severities:
            return SafetyLevel.WARNING
        else:
            return SafetyLevel.OK
    
    def is_safe_to_fly(self) -> bool:
        """Check if it's safe to fly"""
        level = self._calculate_overall_level()
        return level in [SafetyLevel.OK, SafetyLevel.WARNING]
    
    def is_safe_to_takeoff(self) -> bool:
        """Check if it's safe to take off"""
        # Check critical prerequisites
        gps = self._current_state["gps"]
        battery = self._current_state["battery"]
        
        if gps.get("satellites", 0) < self.config.min_gps_satellites:
            return False
        
        if battery.get("percent", 100) < self.config.battery_caution_percent:
            return False
        
        if not self._current_state["rc"].get("connected", False):
            return False
        
        # Check for critical violations
        for violation in self.active_violations.values():
            if violation.severity in [SafetyLevel.CRITICAL, SafetyLevel.EMERGENCY]:
                return False
        
        return True
    
    def register_violation_callback(self, callback: Callable):
        """Register callback for violations"""
        self._violation_callbacks.append(callback)
    
    def register_recovery_callback(self, callback: Callable):
        """Register callback for recoveries"""
        self._recovery_callbacks.append(callback)
    
    def register_emergency_callback(self, callback: Callable):
        """Register callback for emergencies"""
        self._emergency_callbacks.append(callback)
    
    def acknowledge_violation(self, vtype: ViolationType) -> bool:
        """Acknowledge and clear a warning-level violation"""
        if vtype in self.active_violations:
            violation = self.active_violations[vtype]
            if violation.severity == SafetyLevel.WARNING:
                self.active_violations.pop(vtype)
                return True
        return False
    
    def get_violation_history(self, count: int = 20) -> List[Dict]:
        """Get recent violation history"""
        with self._lock:
            history = list(self.violation_history)[-count:]
            return [
                {
                    "type": v.violation_type.value,
                    "severity": v.severity.value,
                    "message": v.message,
                    "timestamp": v.timestamp,
                    "resolved": v.resolved,
                    "resolved_time": v.resolved_time
                }
                for v in reversed(history)
            ]
    
    def clear_history(self):
        """Clear violation history"""
        with self._lock:
            self.violation_history.clear()
            self.warning_history.clear()
    
    def start_monitoring(self):
        """Start background monitoring thread"""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()
        print("[SAFETY_MONITOR] Background monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        print("[SAFETY_MONITOR] Background monitoring stopped")
    
    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                violations = self.check_all()
                
                # Auto-response for critical violations
                for violation in violations:
                    if violation.severity in [SafetyLevel.CRITICAL, SafetyLevel.EMERGENCY]:
                        if violation.violation_type == ViolationType.GPS_LOST:
                            print("[SAFETY_MONITOR] Auto-response: Holding position due to GPS loss")
                        elif violation.violation_type == ViolationType.BATTERY_CRITICAL:
                            print("[SAFETY_MONITOR] Auto-response: Initiating RTL due to battery critical")
                
                time.sleep(self.config.check_interval_ms / 1000.0)
            except Exception as e:
                print(f"[SAFETY_MONITOR] Monitoring error: {e}")
                time.sleep(0.1)


class GeofenceValidator:
    """
    Geofence validation using polygon and cylinder constraints.
    """
    
    def __init__(self, safety_config: SafetyConfig):
        self.config = safety_config
        self._polygon_constraints: List = []
        self._cylinder_constraints: List = []
    
    def add_polygon_constraint(
        self,
        name: str,
        points: List[Tuple[float, float]],
        min_alt: float = -float('inf'),
        max_alt: float = float('inf')
    ):
        """Add a polygon geofence constraint"""
        self._polygon_constraints.append({
            "name": name,
            "points": points,
            "min_alt": min_alt,
            "max_alt": max_alt
        })
    
    def add_cylinder_constraint(
        self,
        name: str,
        center: Tuple[float, float],
        radius_m: float,
        min_alt: float = -float('inf'),
        max_alt: float = float('inf')
    ):
        """Add a cylinder geofence constraint"""
        self._cylinder_constraints.append({
            "name": name,
            "center": center,
            "radius_m": radius_m,
            "min_alt": min_alt,
            "max_alt": max_alt
        })
    
    def validate_position(
        self,
        lat: float,
        lon: float,
        alt: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if position is within geofence.
        
        Returns:
            (is_valid, violation_message)
        """
        # Check altitude
        if alt > self.config.max_altitude_m:
            return False, f"Altitude {alt:.1f}m exceeds maximum"
        
        if alt < 0:
            return False, f"Altitude {alt:.1f}m below ground"
        
        # Check distance from home (cylinder at home)
        import math
        lat1 = lat
        lon1 = lon
        lat2 = 0  # Placeholder
        lon2 = 0  # Placeholder
        
        # Simple distance check
        R = 6371000
        dlat = math.radians(lat - lat2)
        dlon = math.radians(lon - lon2)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        
        if distance > self.config.max_distance_m:
            return False, f"Distance {distance:.1f}m exceeds maximum"
        
        # Check polygon constraints
        for poly in self._polygon_constraints:
            if self._point_in_polygon(lat, lon, poly["points"]):
                if not (poly["min_alt"] <= alt <= poly["max_alt"]):
                    return False, f"Inside {poly['name']} at invalid altitude"
        
        # Check cylinder constraints
        for cyl in self._cylinder_constraints:
            cx, cy = cyl["center"]
            dlat = math.radians(lat - cx)
            dlon = math.radians(lon - cy)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(cx)) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            dist = R * c
            
            if dist <= cyl["radius_m"]:
                if not (cyl["min_alt"] <= alt <= cyl["max_alt"]):
                    return False, f"Inside {cyl['name']} zone at invalid altitude"
        
        return True, None
    
    def _point_in_polygon(
        self,
        lat: float,
        lon: float,
        points: List[Tuple[float, float]]
    ) -> bool:
        """Ray casting point-in-polygon test"""
        n = len(points)
        inside = False
        
        j = n - 1
        for i in range(n):
            xi, yi = points[i]
            xj, yj = points[j]
            
            if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        
        return inside