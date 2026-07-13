"""
SkyCore Real GPS Driver
Real GPS/NMEA parsing for actual GPS modules
"""

import time
import logging
from typing import Dict, Optional, Tuple, List
from threading import Thread, Lock

try:
    import serial
    import pynmea2
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealGPS:
    """
    Real GPS driver using NMEA protocol
    Works with u-blox, Neo, and standard NMEA GPS modules
    """
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 9600):
        if not HAS_PYSERIAL:
            raise RuntimeError("pyserial required: pip install pyserial pynmea2")
            
        self.port = port
        self.baudrate = baudrate
        
        self.serial_port = None
        self.running = False
        self.thread = None
        
        self.lock = Lock()
        
        # GPS data
        self.lat = 0.0
        self.lon = 0.0
        self.alt = 0.0
        self.speed = 0.0
        self.course = 0.0
        self.hdop = 99.0
        self.vdop = 99.0
        self.satellites = 0
        self.fix_type = 0
        
        self.timestamp = 0
        self.valid = False
        
        # Raw sentences for debugging
        self.last_gga = None
        self.last_rmc = None
        
    def connect(self) -> bool:
        """Connect to GPS serial port"""
        try:
            logger.info(f"Connecting to GPS on {self.port} at {self.baudrate} baud")
            
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            self.running = True
            self.thread = Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            
            logger.info("GPS connected")
            return True
            
        except Exception as e:
            logger.error(f"GPS connection failed: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from GPS"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.serial_port:
            self.serial_port.close()
            self.serial_port = None
        logger.info("GPS disconnected")
            
    def _read_loop(self):
        """GPS read loop - runs in background thread"""
        buffer = ""
        
        while self.running:
            try:
                if self.serial_port and self.serial_port.in_waiting:
                    data = self.serial_port.read(self.serial_port.in_waiting).decode('ascii', errors='ignore')
                    buffer += data
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        
                        if line:
                            self._parse_nmea(line)
                            
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"GPS read error: {e}")
                time.sleep(1)
                
    def _parse_nmea(self, sentence: str):
        """Parse NMEA sentence"""
        try:
            if sentence.startswith('$'):
                msg = pynmea2.parse(sentence)
                
                if isinstance(msg, pynmea2.GGA):
                    self._parse_gga(msg)
                    self.last_gga = sentence
                    
                elif isinstance(msg, pynmea2.RMC):
                    self._parse_rmc(msg)
                    self.last_rmc = sentence
                    
                elif isinstance(msg, pynmea2.GSA):
                    self._parse_gsa(msg)
                    
        except Exception as e:
            pass  # Ignore parse errors for invalid sentences
            
    def _parse_gga(self, msg: pynmea2.GGA):
        """Parse GGA (fix data) sentence"""
        with self.lock:
            self.timestamp = time.time()
            
            # Latitude
            if msg.lat and msg.lat_dir:
                self.lat = self._nmea_to_decimal(msg.lat, msg.lat_dir)
                
            # Longitude
            if msg.lon and msg.lon_dir:
                self.lon = self._nmea_to_decimal(msg.lon, msg.lon_dir)
                
            # Altitude
            if msg.altitude:
                self.alt = float(msg.altitude)
                
            # Fix quality
            self.fix_type = int(msg.gps_qual) if msg.gps_qual else 0
            
            # HDOP
            if msg.hdop:
                self.hdop = float(msg.hdop)
                
            # Satellites
            if msg.num_sats:
                self.satellites = int(msg.num_sats)
                
            self.valid = self.fix_type >= 1
            
    def _parse_rmc(self, msg: pynmea2.RMC):
        """Parse RMC (recommended minimum) sentence"""
        with self.lock:
            # Speed in knots
            if msg.spd_over_grnd:
                self.speed = float(msg.spd_over_grnd) * 1.852  # Convert to km/h
                
            # Course/heading
            if msg.true_course:
                self.course = float(msg.true_course)
                
    def _parse_gsa(self, msg: pynmea2.GSA):
        """Parse GSA (DOP and active satellites) sentence"""
        with self.lock:
            # VDOP
            if hasattr(msg, 'vdop') and msg.vdop:
                self.vdop = float(msg.vdop)
                
    def _nmea_to_decimal(self, coord: str, direction: str) -> float:
        """Convert NMEA coordinate to decimal degrees"""
        try:
            # Format: DDMM.MMMMM or DDDMM.MMMMM
            if len(coord) >= 6:
                if direction in ['N', 'S']:
                    # Latitude
                    degrees = int(coord[:2])
                    minutes = float(coord[2:])
                else:
                    # Longitude
                    degrees = int(coord[:3])
                    minutes = float(coord[3:])
                    
                decimal = degrees + minutes / 60.0
                
                if direction in ['S', 'W']:
                    decimal = -decimal
                    
                return decimal
        except:
            pass
        return 0.0
        
    def get_position(self) -> Tuple[float, float, float]:
        """
        Get current position
        
        Returns:
            (latitude, longitude, altitude) in degrees/meters
        """
        with self.lock:
            return (self.lat, self.lon, self.alt)
            
    def get_data(self) -> Dict:
        """
        Get all GPS data
        
        Returns:
            Dictionary with all GPS measurements
        """
        with self.lock:
            return {
                'lat': self.lat,
                'lon': self.lon,
                'alt': self.alt,
                'speed': self.speed,
                'course': self.course,
                'hdop': self.hdop,
                'vdop': self.vdop,
                'satellites': self.satellites,
                'fix_type': self.fix_type,
                'valid': self.valid,
                'timestamp': self.timestamp
            }
            
    def is_fixed(self) -> bool:
        """Check if GPS has valid fix"""
        return self.fix_type >= 2
        
    def wait_for_fix(self, timeout: float = 60.0) -> bool:
        """
        Wait for GPS fix
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            True if fix obtained
        """
        start = time.time()
        
        while time.time() - start < timeout:
            if self.is_fixed():
                return True
            time.sleep(1)
            
        return False


class UBloxGPS(RealGPS):
    """
    u-blox GPS specific driver
    Supports NMEA and UBX protocols
    """
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 9600):
        super().__init__(port, baudrate)
        
        self.geo_sep = 0.0  # Geoidal separation
        
    def configure_ublox(self):
        """Configure u-blox for high performance"""
        if not self.serial_port:
            return
            
        # Configure messages
        commands = [
            # Disable GLONASS NMEA (save bandwidth)
            b'$PUBX,41,1,0007,0001,9600,0*2E\n',
            # Set rate to 5Hz
            b'$PUBX,41,1,0007,0003,19200,0*31\n',
        ]
        
        for cmd in commands:
            self.serial_port.write(cmd)
            time.sleep(0.1)
            
    def get_ubx_data(self) -> Dict:
        """Get u-blox specific data"""
        data = self.get_data()
        data['geo_sep'] = self.geo_sep
        return data


# Example usage
if __name__ == "__main__":
    import sys
    
    port = sys.argv[1] if len(sys.argv) > 1 else "COM3"
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 9600
    
    print(f"Starting GPS on {port} at {baud} baud")
    
    gps = RealGPS(port, baud)
    
    if gps.connect():
        print("GPS connected, waiting for fix...")
        
        # Wait for fix
        if gps.wait_for_fix(timeout=30):
            print("GPS fix acquired!")
        else:
            print("No GPS fix (might be indoors)")
            
        # Print data
        for _ in range(10):
            data = gps.get_data()
            print(f"Position: {data['lat']:.7f}, {data['lon']:.7f}, Alt: {data['alt']:.1f}m")
            print(f"  Fix: {data['fix_type']}, Sats: {data['satellites']}, HDOP: {data['hdop']:.1f}")
            print(f"  Speed: {data['speed']:.1f} km/h, Course: {data['course']:.1f}°")
            print(f"  Valid: {data['valid']}")
            time.sleep(1)
            
        gps.disconnect()
    else:
        print("GPS connection failed!")