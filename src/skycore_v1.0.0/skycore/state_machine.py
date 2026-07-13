"""
SkyCore Flight State Machine
Comprehensive state management for autonomous drone operations.
"""

import time
import threading
from enum import Enum
from typing import Callable, Optional, Dict, List
from dataclasses import dataclass, field
from collections import deque


class FlightState(Enum):
    """All possible flight states"""
    DISARMED = "disarmed"
    ARMED = "armed"
    TAKEOFF = "takeoff"
    HOLD = "hold"
    AUTO = "auto"
    MANUAL = "manual"
    RTL = "return_to_launch"
    LANDING = "landing"
    EMERGENCY_LANDING = "emergency_landing"
    FAILSAFE = "failsafe"
    ESTOP = "emergency_stop"
    UNKNOWN = "unknown"


class TriggerEvent(Enum):
    """State machine trigger events"""
    ARM_REQUEST = "arm_request"
    DISARM_REQUEST = "disarm_request"
    TAKEOFF_CMD = "takeoff_cmd"
    MISSION_START = "mission_start"
    MISSION_END = "mission_end"
    PAUSE = "pause"
    RESUME = "resume"
    RTL_CMD = "rtl_cmd"
    LAND_CMD = "land_cmd"
    E_LAND_CMD = "e_land_cmd"
    ESTOP_CMD = "estop_cmd"
    FAILSAFE_TRIGGER = "failsafe_trigger"
    GPS_LOST = "gps_lost"
    GPS_REGAINED = "gps_regained"
    BATTERY_LOW = "battery_low"
    BATTERY_CRITICAL = "battery_critical"
    RC_LOST = "rc_lost"
    RC_REGAINED = "rc_regained"
    GEOFENCE_VIOLATION = "geofence_violation"
    THREAT_DETECTED = "threat_detected"
    MODE_SWITCH = "mode_switch"
    ARRIVED = "arrived"
    LANDED = "landed"


@dataclass
class StateTransition:
    """State transition record"""
    from_state: FlightState
    to_state: FlightState
    trigger: TriggerEvent
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    reason: str = ""


@dataclass
class SafetyLimits:
    """Safety limits for state machine"""
    max_altitude_m: float = 120.0
    max_distance_m: float = 500.0
    battery_land_percent: float = 10.0
    battery_rtl_percent: float = 20.0
    battery_warning_percent: float = 30.0
    min_gps_sats: int = 8
    rc_timeout_sec: float = 3.0
    gcs_timeout_sec: float = 10.0


class FlightStateMachine:
    """
    Comprehensive flight state machine with safety monitoring and logging.
    
    State Diagram:
    
                    DISARMED <────> ARMED
                         |           |
                         v           v
                   [ARM_REQUEST] [TAKEOFF_CMD]
                         |           |
                         v           v
                       TAKEOFF -----> HOLD
                          |            |
                          v            v
                    +-----+-----+      AUTO
                    |           |        |
                    v           v        v
                 MANUAL     AUTO <-----> HOLD
                    |           |        |
                    v           v        v
                    +--> RTL <--+    LANDING
                    |       |          |
                    v       +-----> LANDING
                E_LAND
                    |
                    v
                ESTOP
    """
    
    def __init__(
        self,
        safety_limits: Optional[SafetyLimits] = None,
        event_callbacks: Optional[Dict[TriggerEvent, List[Callable]]] = None
    ):
        self.state = FlightState.DISARMED
        self.previous_state: Optional[FlightState] = None
        self.state_start_time = time.time()
        self.transition_history: deque = deque(maxlen=100)
        
        self.safety_limits = safety_limits or SafetyLimits()
        self.event_callbacks = event_callbacks or {}
        
        # Telemetry state
        self.position = {"lat": 0.0, "lon": 0.0, "alt": 0.0}
        self.battery_percent = 100.0
        self.gps_satellites = 0
        self.home_position = {"lat": 0.0, "lon": 0.0, "alt": 0.0}
        self.rc_connected = False
        self.gcs_connected = False
        self.mode = "manual"
        
        # Mission tracking
        self.mission_active = False
        self.mission_paused = False
        self.current_waypoint = 0
        self.total_waypoints = 0
        
        # Warnings and alerts
        self.warnings: List[str] = []
        self.alerts: List[str] = []
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Callbacks
        self._state_change_callbacks: List[Callable] = []
        self._safety_callbacks: List[Callable] = []
        
        # Build transition table
        self._transition_table = self._build_transition_table()
        
        self._log_info(f"State machine initialized in {self.state.value} state")
    
    def _build_transition_table(self) -> Dict:
        """Build the state transition table"""
        return {
            # From DISARMED
            (FlightState.DISARMED, TriggerEvent.ARM_REQUEST): FlightState.ARMED,
            (FlightState.DISARMED, TriggerEvent.FAILSAFE_TRIGGER): FlightState.DISARMED,
            
            # From ARMED
            (FlightState.ARMED, TriggerEvent.TAKEOFF_CMD): FlightState.TAKEOFF,
            (FlightState.ARMED, TriggerEvent.DISARM_REQUEST): FlightState.DISARMED,
            (FlightState.ARMED, TriggerEvent.FAILSAFE_TRIGGER): FlightState.DISARMED,
            
            # From TAKEOFF
            (FlightState.TAKEOFF, TriggerEvent.MISSION_START): FlightState.AUTO,
            (FlightState.TAKEOFF, TriggerEvent.PAUSE): FlightState.HOLD,
            (FlightState.TAKEOFF, TriggerEvent.GPS_LOST): FlightState.HOLD,
            (FlightState.TAKEOFF, TriggerEvent.FAILSAFE_TRIGGER): FlightState.HOLD,
            (FlightState.TAKEOFF, TriggerEvent.LAND_CMD): FlightState.LANDING,
            
            # From HOLD
            (FlightState.HOLD, TriggerEvent.MISSION_START): FlightState.AUTO,
            (FlightState.HOLD, TriggerEvent.LAND_CMD): FlightState.LANDING,
            (FlightState.HOLD, TriggerEvent.MODE_SWITCH): FlightState.MANUAL,
            (FlightState.HOLD, TriggerEvent.GPS_LOST): FlightState.HOLD,
            (FlightState.HOLD, TriggerEvent.GPS_REGAINED): FlightState.HOLD,
            (FlightState.HOLD, TriggerEvent.DISARM_REQUEST): FlightState.DISARMED,
            
            # From AUTO
            (FlightState.AUTO, TriggerEvent.PAUSE): FlightState.HOLD,
            (FlightState.AUTO, TriggerEvent.MISSION_END): FlightState.HOLD,
            (FlightState.AUTO, TriggerEvent.LAND_CMD): FlightState.LANDING,
            (FlightState.AUTO, TriggerEvent.MODE_SWITCH): FlightState.MANUAL,
            (FlightState.AUTO, TriggerEvent.RTL_CMD): FlightState.RTL,
            (FlightState.AUTO, TriggerEvent.BATTERY_LOW): FlightState.RTL,
            (FlightState.AUTO, TriggerEvent.FAILSAFE_TRIGGER): FlightState.RTL,
            (FlightState.AUTO, TriggerEvent.GEOFENCE_VIOLATION): FlightState.HOLD,
            (FlightState.AUTO, TriggerEvent.GPS_LOST): FlightState.HOLD,
            (FlightState.AUTO, TriggerEvent.RC_LOST): FlightState.HOLD,
            (FlightState.AUTO, TriggerEvent.DISARM_REQUEST): FlightState.DISARMED,
            
            # From MANUAL
            (FlightState.MANUAL, TriggerEvent.MISSION_START): FlightState.AUTO,
            (FlightState.MANUAL, TriggerEvent.PAUSE): FlightState.HOLD,
            (FlightState.MANUAL, TriggerEvent.LAND_CMD): FlightState.LANDING,
            (FlightState.MANUAL, TriggerEvent.RTL_CMD): FlightState.RTL,
            (FlightState.MANUAL, TriggerEvent.BATTERY_CRITICAL): FlightState.EMERGENCY_LANDING,
            (FlightState.MANUAL, TriggerEvent.GEOFENCE_VIOLATION): FlightState.HOLD,
            (FlightState.MANUAL, TriggerEvent.DISARM_REQUEST): FlightState.DISARMED,
            
            # From RTL
            (FlightState.RTL, TriggerEvent.LAND_CMD): FlightState.LANDING,
            (FlightState.RTL, TriggerEvent.MISSION_END): FlightState.LANDING,
            (FlightState.RTL, TriggerEvent.GPS_LOST): FlightState.EMERGENCY_LANDING,
            (FlightState.RTL, TriggerEvent.BATTERY_CRITICAL): FlightState.EMERGENCY_LANDING,
            (FlightState.RTL, TriggerEvent.ARRIVED): FlightState.LANDING,
            
            # From LANDING
            (FlightState.LANDING, TriggerEvent.MISSION_END): FlightState.HOLD,
            (FlightState.LANDING, TriggerEvent.E_LAND_CMD): FlightState.EMERGENCY_LANDING,
            (FlightState.LANDING, TriggerEvent.LANDED): FlightState.ARMED,
            (FlightState.LANDING, TriggerEvent.DISARM_REQUEST): FlightState.DISARMED,
            
            # From EMERGENCY_LANDING
            (FlightState.EMERGENCY_LANDING, TriggerEvent.ESTOP_CMD): FlightState.ESTOP,
            (FlightState.EMERGENCY_LANDING, TriggerEvent.LANDED): FlightState.ARMED,
            
            # From FAILSAFE
            (FlightState.FAILSAFE, TriggerEvent.GPS_REGAINED): FlightState.HOLD,
            (FlightState.FAILSAFE, TriggerEvent.RC_REGAINED): FlightState.MANUAL,
            (FlightState.FAILSAFE, TriggerEvent.DISARM_REQUEST): FlightState.DISARMED,
        }
    
    def trigger(self, event: TriggerEvent, reason: str = "") -> bool:
        """
        Trigger a state transition event.
        
        Args:
            event: The trigger event
            reason: Optional reason for the transition
            
        Returns:
            True if transition succeeded, False otherwise
        """
        with self._lock:
            current_state = self.state
            
            # Find valid transition
            transition_key = (current_state, event)
            next_state = self._transition_table.get(transition_key)
            
            if next_state is None:
                self._log_warn(
                    f"No transition for {event.value} from {current_state.value}"
                )
                return False
            
            # Check safety constraints
            if not self._check_safety_transition(next_state):
                self._log_warn(
                    f"Safety check failed for transition to {next_state.value}"
                )
                self._trigger_safety_alert(current_state, next_state, event)
                return False
            
            # Execute transition
            self._execute_transition(current_state, next_state, event, reason)
            return True
    
    def _check_safety_transition(self, next_state: FlightState) -> bool:
        """Check if the transition is safe"""
        # GPS checks for CRITICAL flying states only when GPS satellites are known
        if self.gps_satellites > 0 and next_state in [FlightState.TAKEOFF, FlightState.AUTO, FlightState.RTL]:
            if self.gps_satellites < self.safety_limits.min_gps_sats:
                self.warnings.append(
                    f"Insufficient GPS satellites: {self.gps_satellites}"
                )
                # Don't block takeoff/auto/RTL if we have some GPS signal
                if self.gps_satellites < 3:
                    return False
        
        # Battery checks
        if next_state == FlightState.EMERGENCY_LANDING:
            if self.battery_percent < self.safety_limits.battery_land_percent:
                return True  # Always allow emergency landing
        
        # Check altitude constraints (only for flying states)
        if next_state in [FlightState.TAKEOFF, FlightState.AUTO, FlightState.MANUAL, FlightState.RTL]:
            if self.position.get("alt", 0) > self.safety_limits.max_altitude_m:
                self.warnings.append("Altitude exceeds safety limit")
                # Allow if just slightly over (GPS barometer variance)
                if self.position.get("alt", 0) > self.safety_limits.max_altitude_m + 5:
                    return False
        
        # Check distance constraints (only for AUTO)
        if next_state == FlightState.AUTO:
            distance = self._distance_from_home()
            if distance > self.safety_limits.max_distance_m:
                self.warnings.append("Distance from home exceeds safety limit")
                return False
        
        return True
    
    def _distance_from_home(self) -> float:
        """Calculate distance from home position in meters"""
        if not self.home_position:
            return 0.0
        
        lat1 = self.position.get("lat", 0)
        lon1 = self.position.get("lon", 0)
        lat2 = self.home_position.get("lat", 0)
        lon2 = self.home_position.get("lon", 0)
        
        # Haversine formula
        import math
        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        
        a = (math.sin(dphi/2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _execute_transition(
        self,
        current_state: FlightState,
        next_state: FlightState,
        event: TriggerEvent,
        reason: str
    ):
        """Execute the state transition"""
        self._log_info(
            f"State transition: {current_state.value} -> {next_state.value} "
            f"(trigger: {event.value})"
        )
        
        # Record transition
        transition = StateTransition(
            from_state=current_state,
            to_state=next_state,
            trigger=event,
            reason=reason
        )
        self.transition_history.append(transition)
        
        # Update state
        self.previous_state = current_state
        self.state = next_state
        self.state_start_time = time.time()
        
        # Handle callbacks
        self._notify_state_change(current_state, next_state, event)
        
        # Execute event callbacks
        if event in self.event_callbacks:
            for callback in self.event_callbacks[event]:
                try:
                    callback(next_state)
                except Exception as e:
                    self._log_error(f"Callback error: {e}")
    
    def _trigger_safety_alert(
        self,
        current_state: FlightState,
        next_state: FlightState,
        event: TriggerEvent
    ):
        """Trigger safety alert and appropriate response"""
        self.alerts.append(
            f"Safety violation: cannot transition to {next_state.value}"
        )
        
        # Emit safety callbacks
        for callback in self._safety_callbacks:
            try:
                callback(current_state, next_state, event)
            except Exception as e:
                self._log_error(f"Safety callback error: {e}")
        
        # Auto-transition to safe state based on severity
        if self.battery_percent < self.safety_limits.battery_land_percent:
            self._execute_transition(
                current_state,
                FlightState.EMERGENCY_LANDING,
                TriggerEvent.BATTERY_CRITICAL,
                "Battery critical"
            )
        elif self.gps_satellites < self.safety_limits.min_gps_sats:
            self._execute_transition(
                current_state,
                FlightState.HOLD,
                TriggerEvent.GPS_LOST,
                "GPS lost"
            )
    
    def _notify_state_change(
        self,
        from_state: FlightState,
        to_state: FlightState,
        event: TriggerEvent
    ):
        """Notify all registered state change callbacks"""
        for callback in self._state_change_callbacks:
            try:
                callback(from_state, to_state, event)
            except Exception as e:
                self._log_error(f"State change callback error: {e}")
    
    def update_telemetry(
        self,
        position: Optional[Dict] = None,
        battery_percent: Optional[float] = None,
        gps_satellites: Optional[int] = None,
        rc_connected: Optional[bool] = None,
        gcs_connected: Optional[bool] = None,
        mode: Optional[str] = None
    ):
        """Update telemetry data for state machine decisions"""
        with self._lock:
            if position:
                self.position.update(position)
            if battery_percent is not None:
                self.battery_percent = battery_percent
            if gps_satellites is not None:
                if gps_satellites < self.safety_limits.min_gps_sats:
                    if self.gps_satellites >= self.safety_limits.min_gps_sats:
                        self.trigger(TriggerEvent.GPS_LOST, "GPS satellites dropped")
                else:
                    if self.gps_satellites < self.safety_limits.min_gps_sats:
                        self.trigger(TriggerEvent.GPS_REGAINED, "GPS satellites restored")
                self.gps_satellites = gps_satellites
            if rc_connected is not None:
                if not rc_connected and self.rc_connected:
                    self.trigger(TriggerEvent.RC_LOST, "RC connection lost")
                elif rc_connected and not self.rc_connected:
                    self.trigger(TriggerEvent.RC_REGAINED, "RC connection restored")
                self.rc_connected = rc_connected
            if gcs_connected is not None:
                self.gcs_connected = gcs_connected
            if mode is not None:
                if mode != self.mode:
                    self.mode = mode
                    if self.state == FlightState.AUTO:
                        self.trigger(TriggerEvent.MODE_SWITCH, f"Mode changed to {mode}")
            
            # Battery monitoring
            if battery_percent is not None:
                if battery_percent < self.safety_limits.battery_land_percent:
                    self.trigger(TriggerEvent.BATTERY_CRITICAL, "Battery critical")
                elif battery_percent < self.safety_limits.battery_rtl_percent:
                    if self.state == FlightState.AUTO:
                        self.trigger(TriggerEvent.BATTERY_LOW, "Battery low")
    
    def check_geofence(self) -> bool:
        """Check if current position violates geofence"""
        distance = self._distance_from_home()
        altitude = self.position.get("alt", 0)
        
        # Use a margin for the distance check
        max_dist = self.safety_limits.max_distance_m
        max_alt = self.safety_limits.max_altitude_m
        
        # Only check geofence when armed/flying
        if self.state != FlightState.DISARMED:
            if distance > max_dist:
                # Only trigger violation if we're actually flying
                if self.is_flying():
                    self.trigger(TriggerEvent.GEOFENCE_VIOLATION, 
                                f"Distance {distance:.1f}m exceeds limit")
                return False
            
            if altitude > max_alt + 5:  # 5m margin for barometer variance
                if self.is_flying():
                    self.trigger(TriggerEvent.GEOFENCE_VIOLATION,
                                f"Altitude {altitude:.1f}m exceeds limit")
                return False
        
        return True
    
    def get_state_info(self) -> Dict:
        """Get current state machine information"""
        with self._lock:
            return {
                "current_state": self.state.value,
                "previous_state": self.previous_state.value if self.previous_state else None,
                "state_duration_sec": time.time() - self.state_start_time,
                "mode": self.mode,
                "battery_percent": self.battery_percent,
                "gps_satellites": self.gps_satellites,
                "rc_connected": self.rc_connected,
                "gcs_connected": self.gcs_connected,
                "mission_active": self.mission_active,
                "warnings": self.warnings.copy(),
                "alerts": self.alerts.copy(),
                "position": self.position.copy()
            }
    
    def get_state_history(self) -> List[Dict]:
        """Get transition history"""
        with self._lock:
            return [
                {
                    "from": t.from_state.value,
                    "to": t.to_state.value,
                    "trigger": t.trigger.value,
                    "timestamp": t.timestamp,
                    "reason": t.reason
                }
                for t in self.transition_history
            ]
    
    def register_state_change_callback(self, callback: Callable):
        """Register a callback for state changes"""
        self._state_change_callbacks.append(callback)
    
    def register_safety_callback(self, callback: Callable):
        """Register a callback for safety alerts"""
        self._safety_callbacks.append(callback)
    
    def clear_warnings(self):
        """Clear all warnings"""
        self.warnings.clear()
    
    def clear_alerts(self):
        """Clear all alerts"""
        self.alerts.clear()
    
    def force_state(self, state: FlightState, reason: str = "forced"):
        """Force state machine to a specific state (use with caution)"""
        with self._lock:
            self._log_warn(f"Force state to {state.value}: {reason}")
            self._execute_transition(
                self.state,
                state,
                TriggerEvent.FAILSAFE_TRIGGER if state == FlightState.FAILSAFE 
                    else TriggerEvent.MISSION_START,
                reason
            )
    
    def _log_info(self, message: str):
        """Log info message"""
        print(f"[STATE_MACHINE] {message}")
    
    def _log_warn(self, message: str):
        """Log warning message"""
        print(f"[STATE_MACHINE] WARN: {message}")
        self.warnings.append(message)
    
    def _log_error(self, message: str):
        """Log error message"""
        print(f"[STATE_MACHINE] ERROR: {message}")
        self.alerts.append(message)
    
    def is_flying(self) -> bool:
        """Check if drone is in a flying state"""
        return self.state in [
            FlightState.TAKEOFF,
            FlightState.HOLD,
            FlightState.AUTO,
            FlightState.MANUAL,
            FlightState.RTL,
            FlightState.LANDING
        ]
    
    def is_armed(self) -> bool:
        """Check if drone is armed"""
        return self.state not in [FlightState.DISARMED, FlightState.UNKNOWN]
    
    def can_arm(self) -> bool:
        """Check if drone can be armed"""
        return self.state == FlightState.DISARMED
    
    def can_disarm(self) -> bool:
        """Check if drone can be disarmed"""
        return self.state in [FlightState.ARMED, FlightState.HOLD]
    
    def can_takeoff(self) -> bool:
        """Check if drone can take off"""
        return self.state == FlightState.ARMED and self.gps_satellites >= self.safety_limits.min_gps_sats
    
    def emergency_stop(self):
        """Execute emergency stop"""
        self._log_error("EMERGENCY STOP TRIGGERED")
        self.alerts.append("EMERGENCY STOP")
        self._execute_transition(
            self.state,
            FlightState.ESTOP,
            TriggerEvent.ESTOP_CMD,
            "Emergency stop"
        )


class ModeController:
    """
    Mode controller for handling flight mode changes.
    Supports: manual, stabilize, alt-hold, loiter, auto, rtl, land, brake
    """
    
    MODES = ["manual", "stabilize", "althold", "loiter", "auto", "rtl", "land", "brake"]
    
    def __init__(self, state_machine: FlightStateMachine):
        self.state_machine = state_machine
        self._mode_map = {
            "manual": FlightState.MANUAL,
            "stabilize": FlightState.MANUAL,
            "althold": FlightState.HOLD,
            "loiter": FlightState.HOLD,
            "auto": FlightState.AUTO,
            "rtl": FlightState.RTL,
            "land": FlightState.LANDING,
            "brake": FlightState.HOLD
        }
    
    def set_mode(self, mode: str) -> bool:
        """Set flight mode"""
        if mode not in self.MODES:
            self.state_machine._log_warn(f"Unknown mode: {mode}")
            return False
        
        target_state = self._mode_map.get(mode, FlightState.HOLD)
        
        if self.state_machine.state == target_state:
            return True
        
        if mode == "rtl":
            return self.state_machine.trigger(TriggerEvent.RTL_CMD, f"Mode set to {mode}")
        elif mode == "land":
            return self.state_machine.trigger(TriggerEvent.LAND_CMD, f"Mode set to {mode}")
        elif mode == "auto":
            return self.state_machine.trigger(TriggerEvent.MISSION_START, f"Mode set to {mode}")
        else:
            # For manual/stabilize/loiter/brake, transition to appropriate state
            if target_state == FlightState.MANUAL:
                return self.state_machine.trigger(TriggerEvent.MODE_SWITCH, f"Mode set to {mode}")
            elif target_state == FlightState.HOLD:
                return self.state_machine.trigger(TriggerEvent.PAUSE, f"Mode set to {mode}")
        
        return False
    
    def get_current_mode(self) -> str:
        """Get current mode string"""
        state = self.state_machine.state
        
        for mode, target_state in self._mode_map.items():
            if state == target_state:
                return mode
        
        return "unknown"


class FailsafeManager:
    """
    Manages failsafe conditions and responses.
    """
    
    def __init__(self, state_machine: FlightStateMachine, safety_limits: SafetyLimits):
        self.state_machine = state_machine
        self.safety_limits = safety_limits
        self.failsafe_triggers: Dict[str, float] = {}
    
    def trigger_failsafe(self, reason: str) -> bool:
        """Trigger failsafe response"""
        self.failsafe_triggers[reason] = time.time()
        self.state_machine._log_warn(f"Failsafe triggered: {reason}")
        
        # Determine response based on failsafe type
        if "rc_loss" in reason.lower():
            return self.state_machine.trigger(
                TriggerEvent.FAILSAFE_TRIGGER,
                "RC loss failsafe"
            )
        elif "gps_loss" in reason.lower():
            return self.state_machine.trigger(
                TriggerEvent.GPS_LOST,
                "GPS loss failsafe"
            )
        else:
            return self.state_machine.trigger(
                TriggerEvent.FAILSAFE_TRIGGER,
                reason
            )
    
    def check_rc_loss(self, last_rc_time: float) -> bool:
        """Check for RC signal loss"""
        if time.time() - last_rc_time > self.safety_limits.rc_timeout_sec:
            return self.trigger_failsafe("RC signal lost")
        return False
    
    def check_gcs_loss(self, last_gcs_time: float) -> bool:
        """Check for GCS connection loss"""
        if time.time() - last_gcs_time > self.safety_limits.gcs_timeout_sec:
            return self.trigger_failsafe("GCS connection lost")
        return False
    
    def check_battery(self, battery_percent: float) -> bool:
        """Check battery level for failsafe"""
        if battery_percent < self.safety_limits.battery_land_percent:
            return self.trigger_failsafe("Battery critical")
        elif battery_percent < self.safety_limits.battery_rtl_percent:
            if self.state_machine.state == FlightState.AUTO:
                return self.state_machine.trigger(
                    TriggerEvent.BATTERY_LOW,
                    "Battery low warning"
                )
        return False
    
    def get_active_failsafes(self) -> Dict[str, float]:
        """Get active failsafe triggers"""
        return self.failsafe_triggers.copy()
    
    def clear_failsafe(self, reason: str):
        """Clear a failsafe trigger"""
        if reason in self.failsafe_triggers:
            del self.failsafe_triggers[reason]