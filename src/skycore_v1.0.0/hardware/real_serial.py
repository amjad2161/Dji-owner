"""
SkyCore Real Hardware Serial Interface
Real serial port communication for drone hardware
"""

import time
import logging
from typing import Dict, List, Optional, Callable
from threading import Thread, Lock, Event
from queue import Queue, Empty

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SerialPort:
    """
    Real serial port communication
    Handles all serial device communication
    """
    
    def __init__(
        self,
        port: str = None,
        baudrate: int = 115200,
        bytesize: int = 8,
        parity: str = 'N',
        stopbits: float = 1.0,
        timeout: float = 1.0
    ):
        if not HAS_SERIAL:
            raise RuntimeError("pyserial required: pip install pyserial")
            
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        
        self.serial = None
        self.running = False
        self.thread = None
        
        self.read_callback: Optional[Callable] = None
        self.read_queue: Queue = Queue()
        self.lock = Lock()
        
        # Statistics
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packets_sent = 0
        self.packets_received = 0
        self.errors = 0
        
    def open(self, port: str = None) -> bool:
        """
        Open serial port
        
        Args:
            port: Port name (COM3, /dev/ttyUSB0, etc.)
            
        Returns:
            True if opened successfully
        """
        if port:
            self.port = port
            
        if not self.port:
            logger.error("No port specified")
            return False
            
        try:
            logger.info(f"Opening serial port: {self.port} @ {self.baudrate}")
            
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=self.timeout,
                write_timeout=1.0
            )
            
            # Clear buffers
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            self.running = True
            self.thread = Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            
            logger.info(f"Serial port {self.port} opened")
            return True
            
        except Exception as e:
            logger.error(f"Failed to open {self.port}: {e}")
            return False
            
    def close(self):
        """Close serial port"""
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=2)
            
        if self.serial:
            self.serial.close()
            self.serial = None
            
        logger.info(f"Serial port {self.port} closed")
        
    def is_open(self) -> bool:
        """Check if port is open"""
        return self.serial is not None and self.serial.is_open
        
    def _read_loop(self):
        """Background read loop"""
        buffer = b""
        
        while self.running:
            try:
                if self.serial and self.serial.in_waiting > 0:
                    data = self.serial.read(self.serial.in_waiting)
                    self.bytes_received += len(data)
                    buffer += data
                    
                    # Process complete lines
                    while b'\n' in buffer or b'\r' in buffer:
                        if b'\n' in buffer:
                            line, buffer = buffer.split(b'\n', 1)
                        else:
                            line, buffer = buffer.split(b'\r', 1)
                            
                        line = line.strip()
                        if line:
                            self.packets_received += 1
                            
                            # Put in queue
                            self.read_queue.put(line)
                            
                            # Call callback if set
                            if self.read_callback:
                                try:
                                    self.read_callback(line)
                                except Exception as e:
                                    logger.error(f"Callback error: {e}")
                                    
                else:
                    time.sleep(0.01)
                    
            except Exception as e:
                self.errors += 1
                logger.error(f"Read error: {e}")
                time.sleep(0.1)
                
    def write(self, data: bytes) -> int:
        """
        Write data to serial port
        
        Args:
            data: Bytes to write
            
        Returns:
            Number of bytes written
        """
        if not self.is_open():
            return 0
            
        try:
            n = self.serial.write(data)
            self.bytes_sent += n
            self.packets_sent += 1
            return n
        except Exception as e:
            self.errors += 1
            logger.error(f"Write error: {e}")
            return 0
            
    def write_line(self, line: str):
        """Write line with newline"""
        self.write(line.encode('utf-8') + b'\n')
        
    def read(self, size: int = 1) -> Optional[bytes]:
        """Read available bytes"""
        if not self.is_open():
            return None
        return self.serial.read(size)
        
    def read_line(self, timeout: float = 1.0) -> Optional[bytes]:
        """
        Read line with timeout
        
        Returns:
            Line bytes or None on timeout
        """
        try:
            return self.read_queue.get(timeout=timeout)
        except Empty:
            return None
            
    def available(self) -> int:
        """Get number of bytes available"""
        if self.serial:
            return self.serial.in_waiting
        return 0
        
    def get_stats(self) -> Dict:
        """Get port statistics"""
        return {
            'port': self.port,
            'baudrate': self.baudrate,
            'open': self.is_open(),
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'packets_sent': self.packets_sent,
            'packets_received': self.packets_received,
            'errors': self.errors
        }


def list_available_ports() -> List[Dict]:
    """
    List all available serial ports
    
    Returns:
        List of port info dicts
    """
    ports = []
    
    for port_info in serial.tools.list_ports.comports():
        ports.append({
            'port': port_info.device,
            'name': port_info.name,
            'description': port_info.description,
            'hwid': port_info.hwid,
            'vid': port_info.vid,
            'pid': port_info.pid,
            'serial_number': port_info.serial_number
        })
        
    return ports


class HardwareBus:
    """
    Hardware bus for multiple serial devices
    Manages multiple serial connections
    """
    
    def __init__(self):
        self.ports: Dict[str, SerialPort] = {}
        self.lock = Lock()
        
    def add_port(
        self,
        name: str,
        port: str,
        baudrate: int = 115200,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        Add serial port to bus
        
        Args:
            name: Port identifier
            port: Serial port path
            baudrate: Baud rate
            callback: Data callback function
            
        Returns:
            True if added successfully
        """
        with self.lock:
            if name in self.ports:
                logger.warning(f"Port {name} already exists")
                return False
                
            sp = SerialPort(port, baudrate)
            sp.read_callback = callback
            
            if sp.open(port):
                self.ports[name] = sp
                logger.info(f"Added port {name} on {port}")
                return True
                
        return False
        
    def remove_port(self, name: str):
        """Remove port from bus"""
        with self.lock:
            if name in self.ports:
                self.ports[name].close()
                del self.ports[name]
                
    def write(self, name: str, data: bytes) -> int:
        """Write to named port"""
        with self.lock:
            if name in self.ports:
                return self.ports[name].write(data)
        return 0
        
    def read(self, name: str, size: int = 1) -> Optional[bytes]:
        """Read from named port"""
        with self.lock:
            if name in self.ports:
                return self.ports[name].read(size)
        return None
        
    def get_port(self, name: str) -> Optional[SerialPort]:
        """Get port by name"""
        with self.lock:
            return self.ports.get(name)
            
    def close_all(self):
        """Close all ports"""
        with self.lock:
            for name, port in self.ports.items():
                port.close()
            self.ports.clear()


# Example usage
if __name__ == "__main__":
    print("Available serial ports:")
    ports = list_available_ports()
    
    for p in ports:
        print(f"  {p['port']}: {p['description']}")
        
    if not ports:
        print("  No ports found")
        
    # Example: connect to GPS
    print("\nOpening test port...")
    
    # Find GPS port
    gps_port = None
    for p in ports:
        if 'GPS' in p['description'] or 'FTDI' in p['description']:
            gps_port = p['port']
            break
            
    if gps_port:
        sp = SerialPort(gps_port, 9600)
        
        if sp.open():
            print(f"Connected to {gps_port}")
            
            # Read some data
            for _ in range(10):
                line = sp.read_line(timeout=2)
                if line:
                    print(f"  {line.decode('utf-8', errors='ignore').strip()}")
                    
            sp.close()
        else:
            print("Failed to open port")
    else:
        print("No GPS port found")