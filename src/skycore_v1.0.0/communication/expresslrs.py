"""ExpressLRS protocol handler for long-range RC/telemetry.

Implements:
- ELRS protocol structure
- Packet encoding/decoding
- Telemetry parsing
- Link quality monitoring

ExpressLRS is a high-performance RC link protocol
for FPV drones with adaptive hopping and telemetry.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
import struct
import numpy as np


@dataclass
class ELRSConfig:
    """ExpressLRS configuration."""
    # Protocol parameters
    packet_rate: int = 150  # Hz
    uplink_bandwidth: int = 500  # kHz
    
    # Packet structure
    uplink_payload_size: int = 8    # bytes
    downlink_payload_size: int = 10 # bytes
    
    # CRC
    crc_seed: int = 0
    
    # Channels
    num_channels: int = 16
    
    # Telemetry
    telemetry_enabled: bool = True
    telemetry_interval: int = 10  # frames between telemetry


@dataclass
class RCChannels:
    """RC channel values."""
    channels: List[int]  # 0-2000 for each channel
    switch_channels: List[int]  # For 3-position switches
    
    # Packet type
    packet_type: int = 0  # 0=channels, 1=crsf, 2=linkstats
    
    def to_bytes(self) -> bytes:
        """Convert to ExpressLRS packet bytes."""
        # Simplified encoding
        data = bytearray()
        
        for ch in self.channels[:8]:  # First 8 channels
            data.extend(struct.pack('<H', ch))
        
        return bytes(data)


class ELRSProtocol:
    """ExpressLRS protocol handler."""
    
    PROTOCOL_VERSION = 3
    
    # Packet types
    TYPE_RC_CHANNELS = 0x16
    TYPE_LINK_STATS = 0x17
    TYPE_TELEMETRY = 0x18
    TYPE_SETTINGS = 0x19
    TYPE_MSP_DATA = 0x1A
    
    def __init__(self, config: Optional[ELRSConfig] = None):
        self.config = config or ELRSConfig()
        
        # State
        self.sequence_number = 0
        self.last_rssi = 0
        self.link_quality = 0  # 0-100%
        
        # Telemetry buffer
        self.telemetry_data: Dict[int, bytes] = {}
        
        # Statistics
        self.packets_sent = 0
        self.packets_received = 0
        self.crc_failures = 0
    
    def encode_rc_packet(self, channels: List[int]) -> bytes:
        """Encode RC channel packet.
        
        Args:
            channels: Channel values (0-2000)
            
        Returns:
            Encoded packet bytes
        """
        # Header
        packet = bytearray()
        packet.append(0xC8)  # ELRS sync byte
        packet.append(self.TYPE_RC_CHANNELS)
        
        # Sequence number with hop channel
        packet.append(self.sequence_number & 0xFF)
        
        # Channel data (11 bits per channel, packed)
        channel_data = self._pack_channels(channels[:16])
        packet.extend(channel_data)
        
        # CRC (simplified)
        crc = self._calculate_crc(bytes(packet))
        packet.append(crc)
        
        self.sequence_number = (self.sequence_number + 1) % 256
        self.packets_sent += 1
        
        return bytes(packet)
    
    def decode_packet(self, data: bytes) -> Optional[Dict]:
        """Decode received packet.
        
        Args:
            data: Raw packet bytes
            
        Returns:
            Decoded packet data or None
        """
        if len(data) < 4:
            return None
        
        # Check sync byte
        if data[0] != 0xC8:
            return None
        
        packet_type = data[1]
        sequence = data[2]
        
        # Verify CRC
        if self._calculate_crc(data[:-1]) != data[-1]:
            self.crc_failures += 1
            return None
        
        self.packets_received += 1
        
        # Parse based on type
        if packet_type == self.TYPE_RC_CHANNELS:
            return self._parse_rc_channels(data[3:-1])
        elif packet_type == self.TYPE_LINK_STATS:
            return self._parse_link_stats(data[3:-1])
        elif packet_type == self.TYPE_TELEMETRY:
            return self._parse_telemetry(data[3:-1])
        
        return {'type': packet_type, 'sequence': sequence}
    
    def _pack_channels(self, channels: List[int]) -> bytes:
        """Pack 16 channels (11 bits each) into bytes."""
        result = bytearray()
        
        bit_buffer = 0
        bits_in_buffer = 0
        
        for ch in channels[:16]:
            # 11-bit value (0-2047)
            value = min(2047, max(0, ch // 2))  # Convert 0-2000 to 0-1000
            
            bit_buffer |= value << bits_in_buffer
            bits_in_buffer += 11
            
            while bits_in_buffer >= 8:
                result.append(bit_buffer & 0xFF)
                bit_buffer >>= 8
                bits_in_buffer -= 8
        
        # Add remaining bits
        if bits_in_buffer > 0:
            result.append(bit_buffer & 0xFF)
        
        return bytes(result)
    
    def _parse_rc_channels(self, data: bytes) -> Dict:
        """Parse RC channel data."""
        channels = []
        bit_buffer = 0
        
        # Unpack from bits
        for i in range(16):
            if i * 11 < len(data) * 8:
                # Extract 11 bits
                start_bit = i * 11
                byte_idx = start_bit // 8
                bit_offset = start_bit % 8
                
                # Read up to 11 bits
                value = 0
                bits_read = 0
                
                while bits_read < 11 and byte_idx < len(data):
                    bits_available = 8 - bit_offset
                    bits_to_read = min(bits_available, 11 - bits_read)
                    
                    mask = (1 << bits_to_read) - 1
                    value |= (data[byte_idx] >> bit_offset) & mask << bits_read
                    
                    bits_read += bits_to_read
                    bit_offset = 0
                    byte_idx += 1
                
                channels.append(value * 2)  # Back to 0-2000
        
        return {
            'type': 'rc_channels',
            'channels': channels[:16]
        }
    
    def _parse_link_stats(self, data: bytes) -> Dict:
        """Parse link statistics."""
        if len(data) < 6:
            return {}
        
        return {
            'type': 'link_stats',
            'uplink_rssi': data[0],
            'uplink_quality': data[1],
            'uplink_snr': data[2] - 127,  # Signed byte
            'downlink_rssi': data[3],
            'downlink_quality': data[4],
            'antenna_mode': data[5]
        }
    
    def _parse_telemetry(self, data: bytes) -> Dict:
        """Parse telemetry data."""
        if len(data) < 2:
            return {}
        
        telemetry_type = data[0]
        payload = data[1:]
        
        self.telemetry_data[telemetry_type] = payload
        
        return {
            'type': 'telemetry',
            'telemetry_type': telemetry_type,
            'payload': payload
        }
    
    @staticmethod
    def _calculate_crc(data: bytes) -> int:
        """Calculate CRC for packet."""
        crc = 0
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0x8C
                else:
                    crc >>= 1
        return crc & 0xFF
    
    def update_link_quality(self, packet_data: Dict) -> None:
        """Update link quality estimate."""
        if 'uplink_quality' in packet_data:
            self.link_quality = packet_data['uplink_quality']
        
        if 'uplink_rssi' in packet_data:
            self.last_rssi = packet_data['uplink_rssi']
    
    def encode_telemetry(self, sensor_id: int, data: bytes) -> bytes:
        """Encode telemetry packet.
        
        Args:
            sensor_id: Telemetry sensor ID
            data: Telemetry data
            
        Returns:
            Encoded telemetry packet
        """
        packet = bytearray()
        packet.append(0xC8)
        packet.append(self.TYPE_TELEMETRY)
        packet.append(sensor_id)
        
        # Limit payload size
        payload = data[:self.config.downlink_payload_size - 4]
        packet.extend(payload)
        
        # CRC
        crc = self._calculate_crc(bytes(packet))
        packet.append(crc)
        
        return bytes(packet)


class CRSParser:
    """Crossfire (CRSF) protocol parser for ELRS compatibility."""
    
    # CRSF frame types
    FRAME_TYPE_GPS = 0x02
    FRAME_TYPE_BATTERY_SENSOR = 0x08
    FRAME_TYPE_LINK_STATISTICS = 0x14
    FRAME_TYPE_RC_CHANNELS = 0x16
    FRAME_TYPE_ATTITUDE = 0x1E
    FRAME_TYPE_FLIGHT_MODE = 0x21
    
    def __init__(self):
        self.frame_buffer = bytearray()
    
    def parse_byte(self, byte: int) -> List[Dict]:
        """Parse incoming byte stream.
        
        Args:
            byte: Single byte from serial
            
        Returns:
            List of parsed frames
        """
        self.frame_buffer.append(byte)
        
        frames = []
        
        # Look for frame start (0xC8) and end (0x55)
        while len(self.frame_buffer) >= 2:
            if self.frame_buffer[0] == 0xC8:
                # Found start
                frame_length = self.frame_buffer[1]
                
                if len(self.frame_buffer) >= frame_length + 2:
                    # Complete frame
                    frame_data = bytes(self.frame_buffer[:frame_length + 2])
                    parsed = self._parse_frame(frame_data)
                    
                    if parsed:
                        frames.append(parsed)
                    
                    # Remove parsed frame
                    self.frame_buffer = self.frame_buffer[frame_length + 2:]
                else:
                    break
            else:
                # Remove invalid byte
                self.frame_buffer.pop(0)
        
        return frames
    
    def _parse_frame(self, frame: bytes) -> Optional[Dict]:
        """Parse complete CRSF frame."""
        if len(frame) < 4:
            return None
        
        frame_type = frame[2]
        payload = frame[3:-1]  # Exclude type and CRC
        
        if frame_type == self.FRAME_TYPE_GPS:
            return self._parse_gps(payload)
        elif frame_type == self.FRAME_TYPE_LINK_STATISTICS:
            return self._parse_link_stats(payload)
        elif frame_type == self.FRAME_TYPE_ATTITUDE:
            return self._parse_attitude(payload)
        
        return {'type': frame_type, 'raw': payload}
    
    def _parse_gps(self, payload: bytes) -> Dict:
        """Parse GPS frame."""
        if len(payload) < 15:
            return {}
        
        lat = struct.unpack('<i', payload[0:4])[0] / 1e7
        lon = struct.unpack('<i', payload[4:8])[0] / 1e7
        groundspeed = struct.unpack('<H', payload[8:10])[0] / 100.0  # m/s
        heading = struct.unpack('<H', payload[10:12])[0] / 100.0  # degrees
        altitude = struct.unpack('<i', payload[12:16])[0] / 100.0  # meters
        
        return {
            'type': 'gps',
            'latitude': lat,
            'longitude': lon,
            'groundspeed': groundspeed,
            'heading': heading,
            'altitude': altitude
        }
    
    def _parse_link_stats(self, payload: bytes) -> Dict:
        """Parse link statistics."""
        if len(payload) < 10:
            return {}
        
        uplink_rssi = payload[0]
        uplink_quality = payload[1]
        downlink_rssi = payload[2]
        downlink_quality = payload[3]
        snr = payload[4] - 127 if len(payload) > 4 else 0
        
        return {
            'type': 'link_stats',
            'uplink_rssi': uplink_rssi,
            'uplink_quality': uplink_quality,
            'downlink_rssi': downlink_rssi,
            'downlink_quality': downlink_quality,
            'snr': snr
        }
    
    def _parse_attitude(self, payload: bytes) -> Dict:
        """Parse attitude frame."""
        if len(payload) < 6:
            return {}
        
        pitch = struct.unpack('<h', payload[0:2])[0] / 100.0  # degrees
        roll = struct.unpack('<h', payload[2:4])[0] / 100.0
        yaw = struct.unpack('<h', payload[4:6])[0] / 100.0
        
        return {
            'type': 'attitude',
            'pitch': pitch,
            'roll': roll,
            'yaw': yaw
        }


class LinkMonitor:
    """Monitor ExpressLRS link quality."""
    
    def __init__(self):
        self.rssi_history: List[int] = []
        self.quality_history: List[int] = []
        self.max_history = 100
    
    def update(self, uplink_rssi: int, uplink_quality: int) -> None:
        """Update link statistics."""
        self.rssi_history.append(uplink_rssi)
        self.quality_history.append(uplink_quality)
        
        if len(self.rssi_history) > self.max_history:
            self.rssi_history.pop(0)
            self.quality_history.pop(0)
    
    def get_average_rssi(self) -> float:
        """Get average RSSI over history."""
        if not self.rssi_history:
            return -120
        
        return sum(self.rssi_history) / len(self.rssi_history)
    
    def get_average_quality(self) -> float:
        """Get average link quality."""
        if not self.quality_history:
            return 0
        
        return sum(self.quality_history) / len(self.quality_history)
    
    def get_link_health(self) -> str:
        """Get overall link health status."""
        avg_quality = self.get_average_quality()
        avg_rssi = self.get_average_rssi()
        
        if avg_quality > 90 and avg_rssi > -80:
            return "EXCELLENT"
        elif avg_quality > 70 and avg_rssi > -90:
            return "GOOD"
        elif avg_quality > 50 and avg_rssi > -100:
            return "FAIR"
        elif avg_quality > 30:
            return "POOR"
        else:
            return "CRITICAL"


def demo_expresslrs():
    """Demonstrate ExpressLRS protocol."""
    print("=" * 60)
    print("ExpressLRS Protocol Demo")
    print("=" * 60)
    
    # Create protocol
    config = ELRSConfig()
    elrs = ELRSProtocol(config)
    
    # Encode RC channels
    channels = [1000, 1500, 1500, 1500, 1000, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500]
    
    print("\nEncoding RC packet...")
    packet = elrs.encode_rc_packet(channels)
    print(f"  Packet size: {len(packet)} bytes")
    print(f"  Packet hex: {packet.hex()}")
    
    # Decode packet
    print("\nDecoding packet...")
    decoded = elrs.decode_packet(packet)
    print(f"  Decoded: {decoded}")
    
    # Parse with CRSF parser
    print("\n" + "=" * 40)
    print("CRSF Parsing")
    print("=" * 40)
    
    crsf = CRSParser()
    
    # Simulate GPS frame
    gps_frame = bytearray([0xC8, 0x15, 0x02])  # Start, length, type
    lat = int(32.1234567 * 1e7)
    lon = int(35.1234567 * 1e7)
    gps_frame.extend(struct.pack('<i', lat))
    gps_frame.extend(struct.pack('<i', lon))
    gps_frame.extend(struct.pack('<H', 500))  # groundspeed * 100
    gps_frame.extend(struct.pack('<H', 1800))  # heading * 100
    gps_frame.extend(struct.pack('<i', 10000))  # altitude * 100
    gps_frame.append(0x55)  # End byte
    
    frames = crsf.parse_byte(gps_frame[0])
    for byte in gps_frame[1:]:
        frames = crsf.parse_byte(byte)
    
    print(f"  Parsed {len(frames)} frames")
    for frame in frames:
        print(f"  Frame: {frame}")
    
    # Link monitoring
    print("\n" + "=" * 40)
    print("Link Monitoring")
    print("=" * 40)
    
    monitor = LinkMonitor()
    
    # Simulate link
    for i in range(50):
        rssi = -75 + np.random.randint(-10, 5)
        quality = 95 + np.random.randint(-5, 2)
        monitor.update(rssi, quality)
    
    print(f"  Average RSSI: {monitor.get_average_rssi():.1f} dBm")
    print(f"  Average Quality: {monitor.get_average_quality():.1f}%")
    print(f"  Link Health: {monitor.get_link_health()}")
    
    # Telemetry
    print("\n" + "=" * 40)
    print("Telemetry Encoding")
    print("=" * 40)
    
    bat_data = struct.pack('<HH', 1200, 5000)  # voltage, current
    telemetry = elrs.encode_telemetry(0x08, bat_data)
    print(f"  Battery telemetry: {telemetry.hex()}")


if __name__ == "__main__":
    demo_expresslrs()