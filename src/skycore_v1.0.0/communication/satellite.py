"""Satellite communication module for beyond-line-of-sight control.

Implements:
- Iridium satellite modem interface
- Globalstar API integration
- Message queuing and compression
- Connection status monitoring
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
import time
import struct


@dataclass
class SatelliteConfig:
    """Satellite communication configuration."""
    provider: str = "iridium"  # "iridium", "globalstar", "orbcomm"
    
    # Connection parameters
    baud_rate: int = 19200
    timeout: float = 30.0
    
    # Message parameters
    max_message_size: int = 340  # bytes (Iridium SBD)
    compression_enabled: bool = True
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 5.0
    
    # Callbacks
    on_message_received: Optional[callable] = None
    on_connection_changed: Optional[callable] = None


@dataclass
class SatelliteMessage:
    """Satellite message."""
    timestamp: float
    data: bytes
    priority: int = 1  # 1-5, higher = more urgent
    
    # Status
    sent: bool = False
    acknowledged: bool = False
    retry_count: int = 0
    
    # Metadata
    from_id: Optional[str] = None
    to_id: Optional[str] = None


class IridiumModem:
    """Iridium satellite modem interface."""
    
    # AT Commands
    CMD_AT = "AT"
    CMD_SIGNAL = "AT+CSQ"
    CMD_SEND = "AT+SBDWB"
    CMD_RECEIVE = "AT+SBDIX"
    CMD_SIGNAL_CHECK = "AT+SBDC?"
    
    # Status codes
    STATUS_NO_SIGNAL = 0
    STATUS_SIGNAL_POOR = 1
    STATUS_SIGNAL_FAIR = 2
    STATUS_SIGNAL_GOOD = 3
    STATUS_SIGNAL_EXCELLENT = 4
    
    def __init__(self, config: Optional[SatelliteConfig] = None):
        self.config = config or SatelliteConfig()
        
        # Connection state
        self.connected = False
        self.signal_strength = 0
        self.last_check = 0
        
        # Message queues
        self.outgoing_queue: List[SatelliteMessage] = []
        self.incoming_queue: List[SatelliteMessage] = []
        
        # Session tracking
        self.mo_status = 0  # Mobile originated status
        self.mt_status = 0  # Mobile terminated status
    
    def connect(self) -> bool:
        """Connect to Iridium network."""
        # Simulated connection
        print("Connecting to Iridium network...")
        
        # Initialize modem
        if not self._send_command(self.CMD_AT):
            return False
        
        # Check signal
        if not self._check_signal():
            return False
        
        self.connected = True
        print("Iridium connected")
        
        return True
    
    def disconnect(self) -> None:
        """Disconnect from network."""
        self.connected = False
        print("Iridium disconnected")
    
    def _send_command(self, command: str, timeout: float = 5.0) -> bool:
        """Send AT command to modem."""
        # Simulated response
        if command == self.CMD_AT:
            return True
        elif command == self.CMD_SIGNAL:
            self.signal_strength = 4  # Simulated
            return True
        
        return True
    
    def _check_signal(self) -> bool:
        """Check signal strength."""
        self._send_command(self.CMD_SIGNAL)
        return self.signal_strength >= 1
    
    def send_message(self, data: bytes, priority: int = 1) -> bool:
        """Send message via Iridium SBD.
        
        Args:
            data: Message data
            priority: Message priority
            
        Returns:
            True if message queued successfully
        """
        if not self.connected:
            if not self.connect():
                return False
        
        # Create message
        message = SatelliteMessage(
            timestamp=time.time(),
            data=data,
            priority=priority
        )
        
        self.outgoing_queue.append(message)
        print(f"Message queued, queue size: {len(self.outgoing_queue)}")
        
        return True
    
    def send_telemetry(
        self,
        position: Tuple[float, float, float],
        battery: float,
        status: Dict
    ) -> bool:
        """Send telemetry data.
        
        Args:
            position: (lat, lon, alt)
            battery: Battery level 0-1
            status: Status dictionary
            
        Returns:
            True if sent
        """
        # Compress telemetry
        telemetry = self._compress_telemetry(position, battery, status)
        
        return self.send_message(telemetry, priority=2)
    
    def _compress_telemetry(
        self,
        position: Tuple[float, float, float],
        battery: float,
        status: Dict
    ) -> bytes:
        """Compress telemetry into minimal bytes."""
        lat, lon, alt = position
        
        # Encode as binary
        data = bytearray()
        
        # Position (4 bytes each, scaled)
        lat_enc = int((lat + 90) * 10000)
        lon_enc = int((lon + 180) * 10000)
        alt_enc = int(max(-500, min(20000, alt)) * 10)
        
        data.extend(struct.pack('<i', lat_enc))
        data.extend(struct.pack('<i', lon_enc))
        data.extend(struct.pack('<h', alt_enc))
        
        # Battery (1 byte, percentage)
        data.append(int(battery * 100))
        
        # Status flags (1 byte)
        flags = 0
        if status.get('flying', False):
            flags |= 0x01
        if status.get('rtl', False):
            flags |= 0x02
        if status.get('low_battery', False):
            flags |= 0x04
        data.append(flags)
        
        return bytes(data)
    
    def check_messages(self) -> List[SatelliteMessage]:
        """Check for incoming messages."""
        if not self.connected:
            return []
        
        # Simulate checking for messages
        self._send_command(self.CMD_RECEIVE)
        
        # Return incoming queue
        messages = self.incoming_queue.copy()
        self.incoming_queue.clear()
        
        return messages
    
    def get_connection_status(self) -> Dict:
        """Get connection status."""
        return {
            'connected': self.connected,
            'signal_strength': self.signal_strength,
            'signal_quality': self._get_signal_quality(),
            'queue_size': len(self.outgoing_queue),
            'last_check': self.last_check
        }
    
    def _get_signal_quality(self) -> str:
        """Get human-readable signal quality."""
        if self.signal_strength >= 4:
            return "EXCELLENT"
        elif self.signal_strength >= 3:
            return "GOOD"
        elif self.signal_strength >= 2:
            return "FAIR"
        elif self.signal_strength >= 1:
            return "POOR"
        else:
            return "NO SIGNAL"


class GlobalstarModem:
    """Globalstar satellite modem interface."""
    
    def __init__(self, config: Optional[SatelliteConfig] = None):
        self.config = config or SatelliteConfig()
        
        self.connected = False
        self.signal_bars = 0
        
        self.outgoing_queue: List[SatelliteMessage] = []
        self.incoming_queue: List[SatelliteMessage] = []
    
    def connect(self) -> bool:
        """Connect to Globalstar network."""
        print("Connecting to Globalstar network...")
        
        # Simplified connection
        self.connected = True
        self.signal_bars = 3
        
        print("Globalstar connected")
        return True
    
    def send_message(self, data: bytes, priority: int = 1) -> bool:
        """Send message via Globalstar."""
        if not self.connected:
            if not self.connect():
                return False
        
        message = SatelliteMessage(
            timestamp=time.time(),
            data=data,
            priority=priority
        )
        
        self.outgoing_queue.append(message)
        return True
    
    def receive_message(self) -> Optional[SatelliteMessage]:
        """Receive next message."""
        if self.incoming_queue:
            return self.incoming_queue.pop(0)
        return None


class SatelliteManager:
    """Manage satellite communication with fallback."""
    
    def __init__(self, config: Optional[SatelliteConfig] = None):
        self.config = config or SatelliteConfig()
        
        # Primary modem
        if config and config.provider == "globalstar":
            self.modem = GlobalstarModem(config)
        else:
            self.modem = IridiumModem(config)
        
        # Statistics
        self.messages_sent = 0
        self.messages_received = 0
        self.total_bytes_sent = 0
        self.total_cost = 0.0  # USD
    
    def send(
        self,
        data: bytes,
        priority: int = 1,
        retry: bool = True
    ) -> bool:
        """Send message with retry.
        
        Args:
            data: Message data
            priority: Message priority
            retry: Whether to retry on failure
            
        Returns:
            True if sent successfully
        """
        attempts = 0
        max_attempts = self.config.max_retries if retry else 1
        
        while attempts < max_attempts:
            if self.modem.send_message(data, priority):
                self.messages_sent += 1
                self.total_bytes_sent += len(data)
                self.total_cost += len(data) * 0.0005  # Approximate cost
                return True
            
            attempts += 1
            if attempts < max_attempts:
                time.sleep(self.config.retry_delay)
        
        return False
    
    def send_emergency(
        self,
        position: Tuple[float, float, float],
        error_code: int,
        message: str = ""
    ) -> bool:
        """Send emergency beacon.
        
        Args:
            position: GPS position
            error_code: Error code
            message: Optional message
            
        Returns:
            True if sent
        """
        # Create emergency packet
        emergency = bytearray()
        
        # Header
        emergency.append(0xFF)  # Emergency marker
        emergency.append(error_code & 0xFF)
        
        # Position
        lat, lon, alt = position
        emergency.extend(struct.pack('<i', int(lat * 1e6)))
        emergency.extend(struct.pack('<i', int(lon * 1e6)))
        emergency.extend(struct.pack('<h', int(alt)))
        
        # Message (truncated)
        msg_bytes = message.encode('utf-8')[:32]
        emergency.append(len(msg_bytes))
        emergency.extend(msg_bytes)
        
        return self.send(bytes(emergency), priority=5)
    
    def check_and_receive(self) -> List[SatelliteMessage]:
        """Check for incoming messages."""
        messages = self.modem.check_messages()
        self.messages_received += len(messages)
        return messages
    
    def get_status(self) -> Dict:
        """Get comprehensive status."""
        base_status = self.modem.get_connection_status()
        
        return {
            **base_status,
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received,
            'total_bytes': self.total_bytes_sent,
            'estimated_cost': self.total_cost
        }


def demo_satellite():
    """Demonstrate satellite communication."""
    print("=" * 60)
    print("Satellite Communication Demo")
    print("=" * 60)
    
    # Create satellite manager
    config = SatelliteConfig(provider="iridium")
    sat = SatelliteManager(config)
    
    # Connect
    print("\nConnecting to Iridium...")
    connected = sat.modem.connect()
    print(f"  Connected: {connected}")
    
    status = sat.get_status()
    print(f"  Signal: {status['signal_strength']} ({status['signal_quality']})")
    
    # Send telemetry
    print("\n" + "=" * 40)
    print("Sending Telemetry")
    print("=" * 40)
    
    position = (32.0853, 34.7818, 50.0)  # Tel Aviv coordinates
    battery = 0.75
    status_dict = {'flying': True, 'rtl': False, 'low_battery': False}
    
    success = sat.modem.send_telemetry(position, battery, status_dict)
    print(f"  Telemetry sent: {success}")
    
    # Send custom message
    print("\n" + "=" * 40)
    print("Sending Custom Message")
    print("=" * 40)
    
    custom_data = b"Hello from SkyCore!"
    sent = sat.send(custom_data, priority=2)
    print(f"  Message sent: {sent}")
    
    # Emergency beacon
    print("\n" + "=" * 40)
    print("Emergency Beacon Test")
    print("=" * 40)
    
    success = sat.send_emergency(position, error_code=0x01, message="GPS signal lost")
    print(f"  Emergency sent: {success}")
    
    # Status
    print("\n" + "=" * 40)
    print("Communication Status")
    print("=" * 40)
    
    final_status = sat.get_status()
    print(f"  Messages sent: {final_status['messages_sent']}")
    print(f"  Messages received: {final_status['messages_received']}")
    print(f"  Total bytes: {final_status['total_bytes']}")
    print(f"  Estimated cost: ${final_status['estimated_cost']:.4f}")


if __name__ == "__main__":
    demo_satellite()