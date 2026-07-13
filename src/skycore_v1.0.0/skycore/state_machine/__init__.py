"""State Machine package"""

from .drone_fsm import DroneFSM, DroneState, DroneEvent, StateTransition

# Aliases for compatibility with system.py
FlightStateMachine = DroneFSM
FlightState = DroneState
TriggerEvent = DroneEvent

# SafetyLimits - create a placeholder
class SafetyLimits:
    """Safety limits configuration."""
    max_altitude = 120.0
    max_distance = 500.0
    min_battery = 25.0


class ModeController:
    """Controller mode management."""
    
    def __init__(self):
        self.current_mode = "manual"
        self.modes = ["manual", "stabilize", "alt_hold", "pos_hold", "auto", "guided", "rtl"]
    
    def set_mode(self, mode: str) -> bool:
        if mode in self.modes:
            self.current_mode = mode
            return True
        return False
    
    def get_mode(self) -> str:
        return self.current_mode


class FailsafeManager:
    """Failsafe trigger and recovery management."""
    
    def __init__(self):
        self.failsafe_active = False
        self.failsafe_type = None
        self.actions = {}
    
    def trigger_failsafe(self, failsafe_type: str):
        self.failsafe_active = True
        self.failsafe_type = failsafe_type
    
    def resolve(self):
        self.failsafe_active = False
        self.failsafe_type = None

__all__ = ['DroneFSM', 'DroneState', 'DroneEvent', 'StateTransition',
           'FlightStateMachine', 'FlightState', 'TriggerEvent', 'SafetyLimits',
           'ModeController', 'FailsafeManager']