"""Drone Finite State Machine"""

import time
from typing import Dict, Callable, Optional, List
from dataclasses import dataclass
from enum import Enum
import threading

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class DroneState(Enum):
    """Drone states"""
    DISARMED = 'disarmed'
    ARMED = 'armed'
    TAKEOFF = 'takeoff'
    FLYING = 'flying'
    ALT_HOLD = 'altitude_hold'
    POSITION_HOLD = 'position_hold'
    LOITER = 'loiter'
    AUTO = 'auto'
    GUIDED = 'guided'
    RTL = 'rtl'
    LANDING = 'landing'
    EMERGENCY = 'emergency'
    ERROR = 'error'


class DroneEvent(Enum):
    """Drone events"""
    ARM = 'arm'
    DISARM = 'disarm'
    ARM_FAIL = 'arm_fail'
    TAKEOFF = 'takeoff'
    TAKEOFF_COMPLETE = 'takeoff_complete'
    LAND = 'land'
    LAND_COMPLETE = 'land_complete'
    RTL = 'rtl'
    RTL_COMPLETE = 'rtl_complete'
    MODE_CHANGE = 'mode_change'
    ERROR = 'error'
    STABILIZE = 'stabilize'
    GPS_LOCK = 'gps_lock'
    GPS_LOSS = 'gps_loss'
    LOW_BATTERY = 'low_battery'
    GEOFENCE_BREACH = 'geofence_breach'
    EKF_FAIL = 'ekf_fail'
    RC_LOSS = 'rc_loss'
    FENCE_ENABLE = 'fence_enable'


@dataclass
class StateTransition:
    """State transition definition"""
    from_state: DroneState
    to_state: DroneState
    event: DroneEvent
    guard: Optional[Callable] = None
    action: Optional[Callable] = None


class DroneFSM(LoggerMixin):
    """Drone finite state machine with state history"""

    def __init__(self):
        super().__init__()
        self.state = DroneState.DISARMED
        self.previous_state = None
        self.start_time = time.time()
        self.state_start_time = time.time()

        self.transitions: List[StateTransition] = []
        self.state_history: List[tuple] = []
        self.callbacks: Dict[str, List[Callable]] = {
            'state_change': [],
            'transition': [],
            'event': []
        }

        self._lock = threading.RLock()
        self._build_default_transitions()

    def _build_default_transitions(self):
        """Build default state transitions"""
        transitions = [
            # Arming
            (DroneState.DISARMED, DroneState.ARMED, DroneEvent.ARM),
            (DroneState.ARMED, DroneState.DISARMED, DroneEvent.DISARM),
            (DroneState.ARMED, DroneState.ERROR, DroneEvent.ARM_FAIL),

            # Takeoff
            (DroneState.ARMED, DroneState.TAKEOFF, DroneEvent.TAKEOFF),
            (DroneState.TAKEOFF, DroneState.FLYING, DroneEvent.TAKEOFF_COMPLETE),

            # Landing
            (DroneState.FLYING, DroneState.LANDING, DroneEvent.LAND),
            (DroneState.ALT_HOLD, DroneState.LANDING, DroneEvent.LAND),
            (DroneState.POSITION_HOLD, DroneState.LANDING, DroneEvent.LAND),
            (DroneState.LOITER, DroneState.LANDING, DroneEvent.LAND),
            (DroneState.LANDING, DroneState.ARMED, DroneEvent.LAND_COMPLETE),

            # RTL
            (DroneState.FLYING, DroneState.RTL, DroneEvent.RTL),
            (DroneState.ALT_HOLD, DroneState.RTL, DroneEvent.RTL),
            (DroneState.LOITER, DroneState.RTL, DroneEvent.RTL),
            (DroneState.RTL, DroneState.LANDING, DroneEvent.RTL_COMPLETE),

            # Mode changes
            (DroneState.FLYING, DroneState.ALT_HOLD, DroneEvent.MODE_CHANGE),
            (DroneState.FLYING, DroneState.POSITION_HOLD, DroneEvent.MODE_CHANGE),
            (DroneState.FLYING, DroneState.LOITER, DroneEvent.MODE_CHANGE),
            (DroneState.FLYING, DroneState.AUTO, DroneEvent.MODE_CHANGE),

            # Stabilize
            (DroneState.ALT_HOLD, DroneState.FLYING, DroneEvent.STABILIZE),
            (DroneState.POSITION_HOLD, DroneState.FLYING, DroneEvent.STABILIZE),

            # GPS events
            (DroneState.DISARMED, DroneState.ERROR, DroneEvent.GPS_LOSS),

            # Battery
            (DroneState.FLYING, DroneState.RTL, DroneEvent.LOW_BATTERY),
            (DroneState.ALT_HOLD, DroneState.RTL, DroneEvent.LOW_BATTERY),

            # Error/Emergency
            (DroneState.FLYING, DroneState.EMERGENCY, DroneEvent.ERROR),
            (DroneState.EMERGENCY, DroneState.LANDING, DroneEvent.LAND),
            (DroneState.ERROR, DroneState.DISARMED, DroneEvent.DISARM),
        ]

        for from_s, to_s, event in transitions:
            self.transitions.append(StateTransition(from_s, to_s, event))

    def add_transition(self, from_state: DroneState, to_state: DroneState,
                      event: DroneEvent, guard: Callable = None, action: Callable = None):
        """Add custom transition"""
        self.transitions.append(StateTransition(from_state, to_state, event, guard, action))

    def trigger(self, event: DroneEvent, data: Dict = None) -> bool:
        """Trigger an event"""
        with self._lock:
            self._trigger_callback('event', {'event': event, 'state': self.state, 'data': data})

            transition = self._find_transition(event)
            if not transition:
                self.logger.warning(f"No transition for {event} from {self.state}")
                return False

            if transition.guard and not transition.guard(data):
                self.logger.info(f"Transition guard failed for {event}")
                return False

            old_state = self.state
            self.state = transition.to_state
            self.previous_state = old_state

            self.state_history.append((time.time(), old_state, event, transition.to_state))
            self.state_start_time = time.time()

            self._trigger_callback('state_change', {
                'from': old_state,
                'to': self.state,
                'event': event
            })

            self._trigger_callback('transition', {
                'from': old_state,
                'to': self.state,
                'event': event
            })

            if transition.action:
                transition.action(data)

            self.logger.info(f"State: {old_state.value} -> {self.state.value} ({event.value})")
            return True

    def _find_transition(self, event: DroneEvent) -> Optional[StateTransition]:
        """Find valid transition for event from current state"""
        for t in self.transitions:
            if t.from_state == self.state and t.event == event:
                return t
        return None

    def can_trigger(self, event: DroneEvent) -> bool:
        """Check if event can be triggered"""
        return self._find_transition(event) is not None

    def get_available_events(self) -> List[DroneEvent]:
        """Get list of available events from current state"""
        return [t.event for t in self.transitions if t.from_state == self.state]

    def _trigger_callback(self, event: str, data):
        """Trigger registered callbacks"""
        for callback in self.callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"Callback error: {e}")

    def register_callback(self, event: str, callback: Callable):
        """Register callback"""
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)

    def get_state_duration(self) -> float:
        """Get time in current state"""
        return time.time() - self.state_start_time

    def get_total_duration(self) -> float:
        """Get total time in state machine"""
        return time.time() - self.start_time

    def get_history(self, limit: int = 100) -> List[Dict]:
        """Get state history"""
        return [
            {'timestamp': t, 'from': f.value, 'to': to.value, 'event': e.value}
            for t, f, e, to in self.state_history[-limit:]
        ]

    def reset(self):
        """Reset to initial state"""
        self.state = DroneState.DISARMED
        self.previous_state = None
        self.state_start_time = time.time()
        self.start_time = time.time()

    def get_status(self) -> Dict:
        """Get FSM status"""
        return {
            'state': self.state.value,
            'previous_state': self.previous_state.value if self.previous_state else None,
            'state_duration': self.get_state_duration(),
            'total_duration': self.get_total_duration(),
            'available_events': [e.value for e in self.get_available_events()],
            'history_size': len(self.state_history)
        }

    def is_safe_state(self) -> bool:
        """Check if current state is safe for operations"""
        safe_states = [DroneState.DISARMED, DroneState.ARMED, DroneState.LOITER, DroneState.POSITION_HOLD]
        return self.state in safe_states

    def is_flying(self) -> bool:
        """Check if drone is in flying state"""
        flying_states = [DroneState.FLYING, DroneState.ALT_HOLD, DroneState.POSITION_HOLD,
                       DroneState.LOITER, DroneState.AUTO, DroneState.GUIDED, DroneState.TAKEOFF,
                       DroneState.RTL, DroneState.LANDING]
        return self.state in flying_states

    def can_arm(self) -> bool:
        """Check if drone can be armed"""
        return self.state == DroneState.DISARMED

    def can_takeoff(self) -> bool:
        """Check if drone can takeoff"""
        return self.state == DroneState.ARMED

    def emergency(self):
        """Trigger emergency landing"""
        with self._lock:
            self.state = DroneState.EMERGENCY
            self._trigger_callback('state_change', {'from': self.previous_state, 'to': self.state, 'event': 'emergency'})