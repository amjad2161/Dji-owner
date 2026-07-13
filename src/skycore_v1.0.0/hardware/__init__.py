"""
SkyCore Real Hardware Module
Real drivers for actual drone hardware

This module provides real hardware communication:
- MAVLink via pymavlink (real serial/TCP/UDP)
- GPS via pyserial + pynmea2
- Serial communication for any device
- Camera via OpenCV

Based on:
- pymavlink (2.4.49) - Real MAVLink protocol
- pyserial (3.5) - Real serial ports
- pynmea2 - NMEA GPS parsing
- OpenCV (4.13) - Camera access
"""

import logging
from typing import Dict, List

# Version
__version__ = "1.0.0"

# Check dependencies
DEPS = {
    'pymavlink': False,
    'pyserial': False,
    'pynmea2': False,
    'cv2': False
}

try:
    from pymavlink import mavutil
    DEPS['pymavlink'] = True
except:
    pass

try:
    import serial
    DEPS['pyserial'] = True
except:
    pass

try:
    import pynmea2
    DEPS['pynmea2'] = True
except:
    pass

try:
    import cv2
    DEPS['cv2'] = True
except:
    pass

# Report status
for name, available in DEPS.items():
    if available:
        logging.info(f"Hardware {name}: OK")
    else:
        logging.warning(f"Hardware {name}: NOT AVAILABLE")

# Import classes
from .real_mavlink import RealMAVLinkConnection
from .real_gps import RealGPS, UBloxGPS
from .real_serial import SerialPort, HardwareBus, list_available_ports
from .real_camera import RealCamera, VideoRecorder, CameraCalibration

# Export all
__all__ = [
    'RealMAVLinkConnection',
    'RealGPS',
    'UBloxGPS',
    'SerialPort',
    'HardwareBus',
    'list_available_ports',
    'RealCamera',
    'VideoRecorder',
    'CameraCalibration',
    'DEPS'
]


class HardwareChecker:
    """
    Check available hardware
    """
    
    @staticmethod
    def check_all() -> Dict:
        """Check all hardware availability"""
        results = {}
        
        # Check serial ports
        try:
            ports = list_available_ports()
            results['serial_ports'] = [p['port'] for p in ports]
        except:
            results['serial_ports'] = []
            
        # Check cameras
        cameras = []
        for i in range(10):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        cameras.append(i)
                cap.release()
            except:
                pass
        results['cameras'] = cameras
        
        # Check libraries
        results['libraries'] = DEPS.copy()
        
        return results
        
    @staticmethod
    def list_connection_strings() -> List[str]:
        """List possible connection strings"""
        connections = []
        
        # Serial ports
        for port_info in list_available_ports():
            connections.append(f"serial:{port_info['port']}:921600")
            
        # Common TCP/UDP
        connections.extend([
            "tcp:localhost:5760",
            "tcp:localhost:14550",
            "udp:localhost:14550",
            "udp:127.0.0.1:14550"
        ])
        
        return connections


# Example usage
if __name__ == "__main__":
    print("=== SkyCore Hardware Check ===")
    
    checker = HardwareChecker()
    results = checker.check_all()
    
    print(f"\nSerial ports: {results['serial_ports']}")
    print(f"Cameras: {results['cameras']}")
    
    print("\nLibraries:")
    for name, ok in results['libraries'].items():
        status = "OK" if ok else "MISSING"
        print(f"  {name}: {status}")
        
    print("\nConnection strings:")
    for conn in checker.list_connection_strings()[:10]:
        print(f"  {conn}")