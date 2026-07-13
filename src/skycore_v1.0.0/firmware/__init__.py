"""
SkyCore Firmware Integration Module
==================================

Comprehensive integration with all major drone firmwares and GCS systems.

Sources:
- PX4/PX4-Autopilot (11,752 stars) - px4_autopilot.py
- ArduPilot/ardupilot (15,100 stars) - ardupilot_firmware.py
- mavlink/mavlink (protocol) - mavlink_protocol.py
- betaflight/betaflight (10,969 stars) - betaflight_integration.py
- iNavFlight/inav (4,083 stars) - inav_navigation.py
- mavlink/qgroundcontrol (4,591 stars) - qgroundcontrol_integration.py
- ArduPilot/pymavlink (695 stars) - Python MAVLink

Features:
- Universal firmware adapter
- Complete MAVLink 2.0 implementation
- uORB message handling (PX4)
- MSP protocol (Betaflight)
- Navigation state machines (INAV)
- GCS integration (QGC)
- Multi-vehicle support

Total Stars: 45,000+
"""

import logging

# Version
__version__ = "1.0.0"
__firmware_version__ = "2024.1"

# Module exports
from .firmware_adapter import FirmwareAdapter, FirmwareType
from .px4_autopilot import PX4Autopilot, PX4Mixer, PX4EKF2
from .ardupilot_firmware import ArduPilotFirmware, VehicleType, ArduPilotMode, ArduPilotMotor
from .mavlink_protocol import MAVLinkProtocol, MAVLinkRouter, MAVLINK_MSG_ID, MAV_CMD, MAV_FRAME
from .betaflight_integration import BetaflightMSP, CleanFlightMixer
from .inav_navigation import INAVFirmware, INAVMode, INAVMission, INAVWaypoint
from .qgroundcontrol_integration import QGroundControl, QGCMissionPlanner

# Initialize logging
logging.info(f"SkyCore Firmware Module v{__version__} initialized")
logging.info(f"Supported firmwares: PX4, ArduPilot, Betaflight, INAV")
logging.info(f"Supported GCS: QGroundControl")


class SkyCoreFirmwareHub:
    """
    Main firmware integration hub for SkyCore
    
    Provides unified access to all supported firmwares and protocols
    """
    
    def __init__(self):
        self.adapter = FirmwareAdapter()
        self.mavlink = MAVLinkProtocol()
        self.qgc = QGroundControl()
        
        # Connection history
        self.connection_log = []
        
    def auto_detect_firmware(self, device: str = None) -> str:
        """
        Auto-detect connected firmware
        
        Args:
            device: Connection device
            
        Returns:
            Detected firmware type or 'unknown'
        """
        # Try each firmware in order
        firmwares = ["px4", "ardupilot", "betaflight", "inav"]
        
        for fw in firmwares:
            try:
                if self.adapter.connect(fw, device if device else None):
                    status = self.adapter.get_status()
                    if status.get("connected"):
                        logging.info(f"Auto-detected: {fw}")
                        self.connection_log.append({
                            "firmware": fw,
                            "device": device,
                            "timestamp": time.time()
                        })
                        return fw
                # Disconnect and try next
                self.adapter.disconnect()
            except:
                continue
                
        return "unknown"
        
    def get_supported_firmwares(self) -> List[Dict]:
        """Get list of supported firmwares with details"""
        return [
            {
                "name": "PX4 Autopilot",
                "id": "px4",
                "stars": 11752,
                "url": "https://github.com/PX4/PX4-Autopilot",
                "features": ["uORB", "EKF2", "Offboard", "Multi-vehicle"]
            },
            {
                "name": "ArduPilot",
                "id": "ardupilot",
                "stars": 15100,
                "url": "https://github.com/ArduPilot/ardupilot",
                "features": ["Copter", "Plane", "Rover", "Sub", "Mission Planning"]
            },
            {
                "name": "Betaflight",
                "id": "betaflight",
                "stars": 10969,
                "url": "https://github.com/betaflight/betaflight",
                "features": ["MSP", "Blackbox", "OSD", "PID Tuning"]
            },
            {
                "name": "INAV",
                "id": "inav",
                "stars": 4083,
                "url": "https://github.com/iNavFlight/inav",
                "features": ["Navigation", "GPS Waypoints", "RTH", "Geo-fence"]
            }
        ]
        
    def get_connection_stats(self) -> Dict:
        """Get connection statistics"""
        return {
            "total_connections": len(self.connection_log),
            "firmware_counts": self._count_firmwares(),
            "last_connection": self.connection_log[-1] if self.connection_log else None
        }
        
    def _count_firmwares(self) -> Dict[str, int]:
        """Count connections per firmware"""
        counts = {}
        for conn in self.connection_log:
            fw = conn["firmware"]
            counts[fw] = counts.get(fw, 0) + 1
        return counts


# Export all classes
__all__ = [
    # Core
    'SkyCoreFirmwareHub',
    'FirmwareAdapter',
    'FirmwareType',
    
    # PX4
    'PX4Autopilot',
    'PX4Mixer',
    'PX4EKF2',
    
    # ArduPilot
    'ArduPilotFirmware',
    'VehicleType',
    'ArduPilotMode',
    'ArduPilotMotor',
    
    # MAVLink
    'MAVLinkProtocol',
    'MAVLinkRouter',
    'MAVLINK_MSG_ID',
    'MAV_CMD',
    'MAV_FRAME',
    
    # Betaflight
    'BetaflightMSP',
    'CleanFlightMixer',
    
    # INAV
    'INAVFirmware',
    'INAVMode',
    'INAVMission',
    'INAVWaypoint',
    
    # QGC
    'QGroundControl',
    'QGCMissionPlanner'
]