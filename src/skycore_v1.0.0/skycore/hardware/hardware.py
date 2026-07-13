"""
SkyCore Hardware Abstraction Layer
==================================
Hardware interfaces and abstraction.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger(__name__)


class HardwareType(Enum):
    """Hardware component types."""
    IMU = "imu"
    GPS = "gps"
    BAROMETER = "barometer"
    MAGNETOMETER = "magnetometer"
    CAMERA = "camera"
    MOTOR = "motor"
    ESC = "esc"
    BATTERY = "battery"
    RADIO = "radio"
    LED = "led"


@dataclass
class HardwareStatus:
    """Hardware component status."""
    component: HardwareType
    healthy: bool
    temperature_c: float = 25.0
    voltage: float = 0.0
    current_ma: float = 0.0
    firmware_version: str = ""
    last_update: float = 0.0


class HardwareManager:
    """
    Hardware abstraction layer manager.
    
    Provides unified interface for all hardware components.
    """
    
    def __init__(self):
        self.components: Dict[HardwareType, HardwareStatus] = {}
        log.info("Hardware Manager initialized")
    
    def register_component(self, component: HardwareType, status: HardwareStatus):
        """Register hardware component."""
        self.components[component] = status
        log.info(f"Registered {component.value}")
    
    def get_status(self, component: HardwareType) -> Optional[HardwareStatus]:
        """Get component status."""
        return self.components.get(component)
    
    def get_all_status(self) -> Dict[str, bool]:
        """Get status of all components."""
        return {c.value: s.healthy for c, s in self.components.items()}
    
    def is_healthy(self) -> bool:
        """Check if all critical components are healthy."""
        critical = [HardwareType.IMU, HardwareType.GPS, HardwareType.BAROMETER]
        return all(self.components.get(c, HardwareStatus(c, False)).healthy for c in critical)


__all__ = ['HardwareManager', 'HardwareType', 'HardwareStatus']