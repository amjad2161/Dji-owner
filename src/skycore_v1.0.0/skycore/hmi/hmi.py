"""
SkyCore HMI - Human Machine Interface
====================================
User interface components for ground control.
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger(__name__)


class ControlMode(Enum):
    """Control mode selection."""
    MANUAL = "manual"
    ASSISTED = "assisted"
    AUTONOMOUS = "autonomous"
    EMERGENCY = "emergency"


@dataclass
class HMIState:
    """HMI current state."""
    control_mode: ControlMode = ControlMode.ASSISTED
    active_page: str = "dashboard"
    camera_view: str = "fpv"
    overlay_visible: bool = True
    map_zoom: float = 1.0


class HMI:
    """
    Human Machine Interface controller.
    
    Manages:
    - Display state
    - User input processing
    - Audio/visual alerts
    - Mode switching
    """
    
    def __init__(self):
        self.state = HMIState()
        self.subscribers: List[Callable] = []
        log.info("HMI initialized")
    
    def set_control_mode(self, mode: ControlMode):
        """Set control mode."""
        self.state.control_mode = mode
        self._notify()
        log.info(f"Control mode: {mode.value}")
    
    def switch_page(self, page: str):
        """Switch display page."""
        self.state.active_page = page
        self._notify()
    
    def show_alert(self, title: str, message: str, severity: str = "info"):
        """Show alert to user."""
        alert = {'title': title, 'message': message, 'severity': severity}
        for subscriber in self.subscribers:
            try:
                subscriber(alert)
            except Exception as e:
                log.error(f"Alert subscriber error: {e}")
    
    def subscribe(self, callback: Callable):
        """Subscribe to HMI events."""
        self.subscribers.append(callback)
    
    def _notify(self):
        """Notify subscribers of state change."""
        for subscriber in self.subscribers:
            try:
                subscriber(self.state)
            except Exception as e:
                log.error(f"HMI subscriber error: {e}")
    
    def get_state(self) -> Dict:
        """Get current HMI state."""
        return {
            'control_mode': self.state.control_mode.value,
            'active_page': self.state.active_page,
            'camera_view': self.state.camera_view,
            'overlay_visible': self.state.overlay_visible
        }


__all__ = ['HMI', 'HMIState', 'ControlMode']