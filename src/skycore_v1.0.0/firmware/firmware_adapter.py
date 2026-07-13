"""
SkyCore Firmware Adapter Hub
Unified interface for all major drone firmwares

Supports:
- PX4 Autopilot
- ArduPilot (Copter, Plane, Rover, Sub)
- Betaflight/CleanFlight
- INAV Navigation
- MAVLink protocol
- QGroundControl GCS
"""

import logging
from typing import Dict, List, Optional, Any, Tuple, Callable
from enum import Enum


class FirmwareType(Enum):
    """Supported firmware types"""
    PX4 = "px4"
    ARDUPLOT = "ardupilot"
    BETAFLIGHT = "betaflight"
    INAV = "inav"


class FirmwareAdapter:
    """
    Unified adapter for all drone firmwares
    Provides consistent interface regardless of underlying firmware
    """
    
    def __init__(self):
        self.firmware = None
        self.firmware_type: Optional[FirmwareType] = None
        
        # Import all firmware modules
        from .px4_autopilot import PX4Autopilot
        from .ardupilot_firmware import ArduPilotFirmware, VehicleType
        from .betaflight_integration import BetaflightMSP
        from .inav_navigation import INAVFirmware, INAVMode
        
        # Store references
        self._modules = {
            "px4": PX4Autopilot,
            "ardupilot": lambda: ArduPilotFirmware(VehicleType.COPPER),
            "betaflight": BetaflightMSP,
            "inav": INAVFirmware
        }
        
        logging.info("Firmware adapter initialized")
        
    def connect(
        self,
        firmware_type: str,
        device: str = None,
        **kwargs
    ) -> bool:
        """
        Connect to specified firmware
        
        Args:
            firmware_type: Type of firmware (px4, ardupilot, betaflight, inav)
            device: Connection device (serial port, etc.)
            
        Returns:
            True if connected successfully
        """
        ft = firmware_type.lower()
        
        if ft not in self._modules:
            logging.error(f"Unknown firmware: {firmware_type}")
            return False
            
        try:
            if ft == "ardupilot" and "vehicle_type" in kwargs:
                from .ardupilot_firmware import VehicleType as AVT
                vehicle_type = kwargs.get("vehicle_type", "COPPER")
                self.firmware = ArduPilotFirmware(
                    getattr(AVT, vehicle_type, AVT.COPPER)
                )
            else:
                self.firmware = self._modules[ft]()
                
            self.firmware_type = FirmwareType(ft)
            
            if device:
                return self.firmware.connect(device)
            else:
                return True
                
        except Exception as e:
            logging.error(f"Failed to connect {firmware_type}: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from firmware"""
        if self.firmware:
            self.firmware.disconnect()
            
    def get_status(self) -> Dict:
        """Get firmware status"""
        if not self.firmware:
            return {"connected": False}
            
        if self.firmware_type == FirmwareType.PX4:
            return {
                "connected": self.firmware.connected,
                "armed": self.firmware.state.armed,
                "mode": self.firmware.state.flight_mode
            }
        elif self.firmware_type == FirmwareType.ARDUPLOT:
            return {
                "connected": self.firmware.connected,
                "armed": self.firmware.armed,
                "mode": self.firmware.flight_mode
            }
        elif self.firmware_type == FirmwareType.BETAFLIGHT:
            return {
                "connected": self.firmware.connected,
                "variant": self.firmware.fc_variant,
                "version": self.firmware.fc_version
            }
        elif self.firmware_type == FirmwareType.INAV:
            return {
                "connected": self.firmware.connected,
                "mode": self.firmware.current_mode.name,
                "state": self.firmware.nav_state.name
            }
            
        return {}
        
    # Universal commands
    def arm(self) -> bool:
        """Arm the vehicle"""
        if not self.firmware:
            return False
        return self.firmware.arm() if hasattr(self.firmware, 'arm') else False
        
    def disarm(self) -> bool:
        """Disarm the vehicle"""
        if not self.firmware:
            return False
        return self.firmware.disarm() if hasattr(self.firmware, 'disarm') else False
        
    def set_mode(self, mode: str) -> bool:
        """Set flight mode"""
        if not self.firmware:
            return False
            
        if self.firmware_type == FirmwareType.PX4:
            return self.firmware.set_mode(mode)
        elif self.firmware_type == FirmwareType.ARDUPLOT:
            return self.firmware.set_mode(mode)
        elif self.firmware_type == FirmwareType.INAV:
            from .inav_navigation import INAVMode
            try:
                mode_enum = INAVMode[mode.upper()]
                self.firmware.set_nav_mode(mode_enum)
                return True
            except:
                return False
                
        return False
        
    def upload_mission(self, waypoints: List[Dict]) -> bool:
        """Upload mission to vehicle"""
        if not self.firmware:
            return False
            
        if self.firmware_type == FirmwareType.PX4:
            return self.firmware.upload_mission(waypoints)
        elif self.firmware_type == FirmwareType.ARDUPLOT:
            return self.firmware.upload_mission(waypoints)
            
        return False
        
    def get_position(self) -> Tuple[float, float, float]:
        """Get current position"""
        if not self.firmware:
            return (0, 0, 0)
            
        if self.firmware_type == FirmwareType.PX4:
            return self.firmware.state.position
        elif self.firmware_type == FirmwareType.ARDUPLOT:
            lat = self.firmware.ahrs.lat / 1e7
            lon = self.firmware.ahrs.lng / 1e7
            alt = self.firmware.ahrs.alt / 100
            return (lat, lon, alt)
        elif self.firmware_type == FirmwareType.INAV:
            return (
                self.firmware.position.gps_lat,
                self.firmware.position.gps_lon,
                self.firmware.position.gps_alt
            )
            
        return (0, 0, 0)
        
    def get_attitude(self) -> Tuple[float, float, float]:
        """Get current attitude (roll, pitch, yaw)"""
        if not self.firmware:
            return (0, 0, 0)
            
        if self.firmware_type == FirmwareType.PX4:
            return self.firmware.state.attitude_euler
        elif self.firmware_type == FirmwareType.ARDUPLOT:
            return (
                self.firmware.ahrs.roll,
                self.firmware.ahrs.pitch,
                self.firmware.ahrs.yaw
            )
            
        return (0, 0, 0)
        
    def get_battery(self) -> Dict:
        """Get battery status"""
        if not self.firmware:
            return {}
            
        if self.firmware_type == FirmwareType.PX4:
            return {
                "voltage": self.firmware.sensors.baro_pressure_pa / 1000,
                "remaining": 100
            }
        elif self.firmware_type == FirmwareType.ARDUPLOT:
            return {
                "voltage": self.firmware.battery.voltage,
                "current": self.firmware.battery.current,
                "remaining": self.firmware.battery.remaining
            }
            
        return {}
        
    def set_param(self, name: str, value: float) -> bool:
        """Set parameter"""
        if not self.firmware:
            return False
        return self.firmware.set_param(name, value) if hasattr(self.firmware, 'set_param') else False
        
    def get_param(self, name: str) -> Optional[float]:
        """Get parameter"""
        if not self.firmware:
            return None
        return self.firmware.get_param(name) if hasattr(self.firmware, 'get_param') else None


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    adapter = FirmwareAdapter()
    
    # Connect to PX4
    if adapter.connect("px4"):
        print("Connected to PX4")
        
        # Universal operations
        adapter.arm()
        adapter.set_mode("OFFBOARD")
        
        pos = adapter.get_position()
        print(f"Position: {pos}")
        
        adapter.disconnect()
        
    # Connect to ArduPilot
    if adapter.connect("ardupilot", vehicle_type="COPPER"):
        print("Connected to ArduPilot")
        adapter.set_mode("AUTO")
        adapter.disconnect()
        
    # Connect to Betaflight
    if adapter.connect("betaflight"):
        print("Connected to Betaflight")
        config = adapter.firmware.load_config()
        print(f"Roll rate: {config.roll_rate}")
        adapter.disconnect()
        
    # Connect to INAV
    if adapter.connect("inav"):
        print("Connected to INAV")
        from inav_navigation import INAVMode
        adapter.firmware.set_nav_mode(INAVMode.RTH)
        adapter.disconnect()