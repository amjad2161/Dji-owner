"""MAVLink protocol handler for drone communication.

Implements:
- MAVLink 2.0 protocol
- Message encoding/decoding
- Heartbeat and telemetry
- Command handling
- Parameter protocol

References:
  - MAVLink Protocol: https://mavlink.io/
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Callable
from enum import IntEnum
import struct
import numpy as np
from numpy.typing import NDArray


# MAVLink message IDs
class MAV_MSG(IntEnum):
    HEARTBEAT = 0
    SYSTEM_TIME = 2
    GPS_RAW_INT = 24
    ATTITUDE = 30
    GPS_GLOBAL_ORIGIN = 49
    HOME_POSITION = 242
    SET_MODE = 11
    COMMAND_LONG = 76
    COMMAND_ACK = 77
    PARAM_SET = 23
    PARAM_READ = 20
    PARAM_VALUE = 21
    MANUAL_CONTROL = 69
    RC_CHANNELS = 35
    ACTUATOR_OUTPUT_STATUS = 251
    HIGHRES_IMU = 105
    SCALED_PRESSURE = 29
    BATTERY_STATUS = 370
    STATUSTEXT = 191
    

# MAVLink system types
class MAV_TYPE(IntEnum):
    GENERIC = 0
    FIXED_WING = 1
    QUADROTOR = 2
    COAXIAL = 3
    HELICOPTER = 4
    GROUND = 12
    GCS = 18
    

class MAV_AUTOPILOT(IntEnum):
    GENERIC = 0
    PX4 = 12
    ARDUPILOTMEGA = 3
    

class MAV_MODE_FLAG(IntEnum):
    CUSTOM_MODE = 1
    TEST = 2
    AUTO = 4
    GUIDED = 8
    STABILIZE = 16
    HIL = 64
    

class MAV_STATE(IntEnum):
    UNINIT = 0
    BOOT = 1
    ACTIVE = 4
    STANDBY = 3
    SHUTDOWN = 6
    

@dataclass
class Message:
    """MAVLink message."""
    msg_id: int
    payload: bytes
    system_id: int = 1
    component_id: int = 1
    
    def encode(self) -> bytes:
        """Encode message to bytes."""
        # MAVLink 2.0 header
        header = bytes([0xFD])  # Start marker
        header += struct.pack('B', len(self.payload))  # Length
        header += struct.pack('B', 0)  # Incompat flags
        header += struct.pack('B', 0)  # Compat flags
        header += struct.pack('B', self.sequence)
        header += struct.pack('B', self.system_id)
        header += struct.pack('B', self.component_id)
        header += struct.pack('I', self.msg_id)  # Message ID (3 bytes actually)
        
        # CRC calculation
        crc = self._calculate_crc(self.payload)
        
        return header + self.payload + struct.pack('<H', crc)


@dataclass
class Heartbeat:
    """Heartbeat message (MAV_TYPE, autopilot, mode, custom_mode, state)."""
    type: int = MAV_TYPE.QUADROTOR
    autopilot: int = MAV_AUTOPILOT.GENERIC
    base_mode: int = 0
    custom_mode: int = 0
    system_status: int = MAV_STATE.ACTIVE
    
    def encode(self) -> bytes:
        return struct.pack('<IIII', self.type, self.autopilot, self.base_mode, self.custom_mode)


@dataclass
class Attitude:
    """Attitude message (roll, pitch, yaw, roll rate, pitch rate, yaw rate)."""
    time_boot_ms: int
    roll: float     # rad
    pitch: float    # rad
    yaw: float      # rad
    rollspeed: float # rad/s
    pitchspeed: float
    yawpeed: float
    
    def encode(self) -> bytes:
        return struct.pack('<Iffff', self.time_boot_ms, self.roll, self.pitch, self.yaw,
                         self.rollspeed, self.pitchspeed, self.yawpeed)


@dataclass
class GPSRaw:
    """GPS raw data message."""
    time_usec: int
    fix_type: int      # 0 = no fix, 2 = 2D fix, 3 = 3D fix, 4 = RTK
    lat: int           # degE7
    lon: int           # degE7
    alt: int           # mm
    eph: int           # cm
    epv: int           # cm
    vel: int           # cm/s
    cog: int           # degE5
    satellites_visible: int
    
    def encode(self) -> bytes:
        return struct.pack('<QBIiiIHHHH', self.time_usec, self.fix_type, self.lat, self.lon,
                         self.alt, self.eph, self.epv, self.vel, self.cog, self.satellites_visible)


@dataclass 
class BatteryStatus:
    """Battery status message."""
    id: int = 0
    battery_function: int = 0
    type: int = 3  # LiPo
    temperature: int = 0  # celsius * 100
    voltages: List[int] = field(default_factory=lambda: [0] * 10)
    current: int = -1   # mA, -1 = not used
    current_consumed: int = -1  # mAh
    energy_consumed: int = -1   # hJ
    battery_remaining: int = -1  # %
    
    def encode(self) -> bytes:
        voltage_array = struct.pack('<10H', *self.voltages)
        return struct.pack('<BBhi', self.id, self.battery_function, self.type, self.temperature) + \
               voltage_array + \
               struct.pack('<ii', self.current, self.current_consumed) + \
               struct.pack('<i', self.energy_consumed) + \
               struct.pack('<b', self.battery_remaining) + \
               struct.pack('<3i', 0, 0, 0)  # charge_consumer


@dataclass
class CommandLong:
    """Command long message for sending commands."""
    command: int
    confirmation: int = 0
    param1: float = 0
    param2: float = 0
    param3: float = 0
    param4: float = 0
    param5: float = 0
    param6: float = 0
    param7: float = 0
    
    # Command IDs
    NAV_WAYPOINT = 16
    NAV_LOITER_TIME = 17
    NAV_RETURN_TO_LAUNCH = 20
    NAV_LAND = 21
    NAV_TAKEOFF = 22
    COMPONENT_ARM_DISARM = 400
    FACTORY_RESET = 241
    REBOOT = 246
    
    def encode(self) -> bytes:
        return struct.pack('<BBfffffffI', 0, self.confirmation, self.param1, self.param2,
                         self.param3, self.param4, self.param5, self.param6, self.param7, self.command)


@dataclass
class SetMode:
    """Set mode command."""
    target_system: int = 1
    base_mode: int = 0
    custom_mode: int = 0
    
    # Flight modes
    MODE_MANUAL = 0
    MODE_STABILIZE = 1
    MODE_ACRO = 2
    MODE_ALT_HOLD = 3
    MODE_AUTO = 4
    MODE_GUIDED = 5
    MODE_LOITER = 6
    MODE_RTL = 7
    MODE_CIRCLE = 9
    MODE_LAND = 10
    MODE_GUIDED_NOGPS = 15
    
    def encode(self) -> bytes:
        return struct.pack('<BBI', self.target_system, self.base_mode, self.custom_mode)


class MAVLinkParser:
    """Parse incoming MAVLink messages."""
    
    def __init__(self):
        self.buffer = bytearray()
        self.sequence = 0
        
        # Message handlers
        self.handlers: Dict[int, List[Callable]] = {}
        
        # Statistics
        self.messages_received = 0
        self.messages_failed = 0
    
    def add_handler(self, msg_id: int, handler: Callable) -> None:
        """Add message handler."""
        if msg_id not in self.handlers:
            self.handlers[msg_id] = []
        self.handlers[msg_id].append(handler)
    
    def parse(self, data: bytes) -> List[Dict]:
        """Parse incoming data and return messages.
        
        Returns:
            List of parsed message dictionaries
        """
        self.buffer.extend(data)
        messages = []
        
        while len(self.buffer) >= 12:  # Minimum header size
            # Look for MAVLink 2.0 marker
            if self.buffer[0] != 0xFD:
                self.buffer.pop(0)
                continue
            
            # Parse header
            payload_len = self.buffer[1]
            incompat_flags = self.buffer[2]
            compat_flags = self.buffer[3]
            sequence = self.buffer[4]
            system_id = self.buffer[5]
            component_id = self.buffer[6]
            msg_id = struct.unpack('<I', bytes(self.buffer[7:10]) + b'\x00')[0]
            
            # Check if we have full message
            message_len = 12 + payload_len + 2  # header + payload + CRC
            if len(self.buffer) < message_len:
                break
            
            # Extract payload
            payload = bytes(self.buffer[12:12 + payload_len])
            crc16 = struct.unpack('<H', bytes(self.buffer[12 + payload_len:12 + payload_len + 2]))[0]
            
            # Verify CRC (simplified)
            expected_crc = self._calculate_crc(bytes([payload_len, incompat_flags, compat_flags]) + 
                                                   bytes([sequence, system_id, component_id]) + 
                                                   bytes(self.buffer[7:10]) + payload)
            
            if crc16 != expected_crc:
                self.messages_failed += 1
                self.buffer = self.buffer[message_len:]
                continue
            
            # Parse payload based on message ID
            msg_dict = self._parse_payload(msg_id, payload)
            msg_dict['system_id'] = system_id
            msg_dict['component_id'] = component_id
            msg_dict['sequence'] = sequence
            
            messages.append(msg_dict)
            self.messages_received += 1
            
            # Call handlers
            if msg_id in self.handlers:
                for handler in self.handlers[msg_id]:
                    handler(msg_dict)
            
            # Remove parsed message
            self.buffer = self.buffer[message_len:]
        
        return messages
    
    def _calculate_crc(self, data: bytes) -> int:
        """Calculate MAVLink CRC16."""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    def _parse_payload(self, msg_id: int, payload: bytes) -> Dict:
        """Parse payload based on message ID."""
        parsers = {
            MAV_MSG.HEARTBEAT: self._parse_heartbeat,
            MAV_MSG.ATTITUDE: self._parse_attitude,
            MAV_MSG.GPS_RAW_INT: self._parse_gps_raw,
            MAV_MSG.BATTERY_STATUS: self._parse_battery,
            MAV_MSG.MANUAL_CONTROL: self._parse_manual_control,
            MAV_MSG.COMMAND_ACK: self._parse_command_ack,
        }
        
        parser = parsers.get(msg_id, self._parse_generic)
        return parser(payload)
    
    def _parse_heartbeat(self, payload: bytes) -> Dict:
        return {
            'type': struct.unpack('<I', payload[0:4])[0],
            'autopilot': struct.unpack('<I', payload[4:8])[0],
            'base_mode': struct.unpack('<I', payload[8:12])[0],
            'custom_mode': struct.unpack('<I', payload[12:16])[0],
            'system_status': struct.unpack('<I', payload[16:20])[0] if len(payload) >= 20 else 0,
        }
    
    def _parse_attitude(self, payload: bytes) -> Dict:
        if len(payload) < 28:
            return {}
        return {
            'time_boot_ms': struct.unpack('<I', payload[0:4])[0],
            'roll': struct.unpack('<f', payload[4:8])[0],
            'pitch': struct.unpack('<f', payload[8:12])[0],
            'yaw': struct.unpack('<f', payload[12:16])[0],
            'rollspeed': struct.unpack('<f', payload[16:20])[0],
            'pitchspeed': struct.unpack('<f', payload[20:24])[0],
            'yawspeed': struct.unpack('<f', payload[24:28])[0],
        }
    
    def _parse_gps_raw(self, payload: bytes) -> Dict:
        if len(payload) < 30:
            return {}
        return {
            'time_usec': struct.unpack('<Q', payload[0:8])[0],
            'fix_type': payload[8],
            'lat': struct.unpack('<i', payload[9:13])[0],
            'lon': struct.unpack('<i', payload[13:17])[0],
            'alt': struct.unpack('<i', payload[17:21])[0],
            'eph': struct.unpack('<H', payload[21:23])[0],
            'epv': struct.unpack('<H', payload[23:25])[0],
            'vel': struct.unpack('<H', payload[25:27])[0],
            'cog': struct.unpack('<H', payload[27:29])[0],
            'satellites_visible': payload[29] if len(payload) > 29 else 0,
        }
    
    def _parse_battery(self, payload: bytes) -> Dict:
        return {
            'id': payload[0],
            'battery_remaining': struct.unpack('<b', payload[9:10])[0] if len(payload) > 9 else -1,
        }
    
    def _parse_manual_control(self, payload: bytes) -> Dict:
        if len(payload) < 18:
            return {}
        return {
            'x': struct.unpack('<h', payload[0:2])[0],
            'y': struct.unpack('<h', payload[2:4])[0],
            'z': struct.unpack('<h', payload[4:6])[0],
            'r': struct.unpack('<h', payload[6:8])[0],
            'buttons': struct.unpack('<H', payload[8:10])[0],
        }
    
    def _parse_command_ack(self, payload: bytes) -> Dict:
        return {
            'command': struct.unpack('<H', payload[0:2])[0],
            'result': payload[2] if len(payload) > 2 else 0,
        }
    
    def _parse_generic(self, payload: bytes) -> Dict:
        return {'raw': payload.hex()}


class MAVLinkConnection:
    """MAVLink connection handler."""
    
    def __init__(self, system_id: int = 1, component_id: int = 1):
        self.system_id = system_id
        self.component_id = component_id
        self.parser = MAVLinkParser()
        self.sequence = 0
        
        # Connection state
        self.connected = False
        self.last_heartbeat = 0
        self.timeout = 5.0  # seconds
        
        # Parameters
        self.params: Dict[str, float] = {}
    
    def send_heartbeat(self, connection) -> None:
        """Send heartbeat message."""
        hb = Heartbeat(
            type=MAV_TYPE.QUADROTOR,
            autopilot=MAV_AUTOPILOT.PX4,
            base_mode=MAV_MODE_FLAG.CUSTOM_MODE | MAV_MODE_FLAG.AUTO,
            custom_mode=4,  # Auto mode
            system_status=MAV_STATE.ACTIVE
        )
        self.send_message(MAV_MSG.HEARTBEAT, hb.encode(), connection)
    
    def send_attitude(
        self,
        connection,
        roll: float,
        pitch: float,
        yaw: float
    ) -> None:
        """Send attitude telemetry."""
        import time
        att = Attitude(
            time_boot_ms=int(time.time() * 1000),
            roll=roll, pitch=pitch, yaw=yaw,
            rollspeed=0, pitchspeed=0, yawpeed=0
        )
        self.send_message(MAV_MSG.ATTITUDE, att.encode(), connection)
    
    def send_gps_raw(
        self,
        connection,
        lat: float,
        lon: float,
        alt: float,
        fix_type: int = 3
    ) -> None:
        """Send GPS raw data."""
        import time
        gps = GPSRaw(
            time_usec=int(time.time() * 1e6),
            fix_type=fix_type,
            lat=int(lat * 1e7),
            lon=int(lon * 1e7),
            alt=int(alt * 1000),
            eph=100,
            epv=100,
            vel=0,
            cog=0,
            satellites_visible=12
        )
        self.send_message(MAV_MSG.GPS_RAW_INT, gps.encode(), connection)
    
    def send_battery(
        self,
        connection,
        voltage: float,
        current: float,
        remaining: int
    ) -> None:
        """Send battery status."""
        voltages = [int(voltage * 1000)] + [0] * 9
        bat = BatteryStatus(
            voltages=voltages,
            current=int(current * 100),
            battery_remaining=remaining
        )
        self.send_message(MAV_MSG.BATTERY_STATUS, bat.encode(), connection)
    
    def send_command_long(
        self,
        connection,
        command: int,
        param1: float = 0,
        param2: float = 0,
        param3: float = 0,
        param4: float = 0,
        param5: float = 0,
        param6: float = 0,
        param7: float = 0
    ) -> None:
        """Send command long."""
        cmd = CommandLong(
            command=command,
            param1=param1, param2=param2, param3=param3,
            param4=param4, param5=param5, param6=param6, param7=param7
        )
        self.send_message(MAV_MSG.COMMAND_LONG, cmd.encode(), connection)
    
    def send_set_mode(self, connection, mode: int) -> None:
        """Send set mode command."""
        sm = SetMode(custom_mode=mode)
        self.send_message(MAV_MSG.SET_MODE, sm.encode(), connection)
    
    def send_message(self, msg_id: int, payload: bytes, connection) -> None:
        """Send MAVLink message."""
        # MAVLink 2.0 encoding
        header = bytes([0xFD])  # Start
        header += struct.pack('B', len(payload))
        header += bytes([0, 0])  # Incompat, compat flags
        header += struct.pack('B', self.sequence)
        header += struct.pack('B', self.system_id)
        header += struct.pack('B', self.component_id)
        header += bytes([msg_id & 0xFF, (msg_id >> 8) & 0xFF, (msg_id >> 16) & 0xFF])
        
        # CRC
        crc_data = bytes([len(payload), 0, 0, self.sequence, self.system_id, self.component_id,
                         msg_id & 0xFF, (msg_id >> 8) & 0xFF, (msg_id >> 16) & 0xFF]) + payload
        crc = self.parser._calculate_crc(crc_data)
        
        packet = header + payload + struct.pack('<H', crc)
        
        # Send (would use actual connection)
        # connection.write(packet)
        self.sequence = (self.sequence + 1) % 256
    
    def request_mission_list(self, connection) -> None:
        """Request mission list from FC."""
        self.send_command_long(connection, 0, param5=0, param6=0, param7=0)
    
    def arm(self, connection, arm: bool = True) -> None:
        """Arm or disarm motors."""
        self.send_command_long(connection, CommandLong.COMPONENT_ARM_DISARM, 
                              param1=1 if arm else 0)


def demo_mavlink():
    """Demonstrate MAVLink handling."""
    print("=" * 60)
    print("MAVLink Protocol Demo")
    print("=" * 60)
    
    # Create connection
    conn = MAVLinkConnection(system_id=255, component_id=1)
    
    # Create parser
    parser = MAVLinkParser()
    
    # Add handlers
    def handle_heartbeat(msg):
        print(f"Heartbeat: type={msg.get('type')}, mode={msg.get('base_mode')}")
    
    def handle_gps(msg):
        lat = msg.get('lat', 0) / 1e7
        lon = msg.get('lon', 0) / 1e7
        print(f"GPS: lat={lat:.6f}, lon={lon:.6f}, fix={msg.get('fix_type')}")
    
    parser.add_handler(MAV_MSG.HEARTBEAT, handle_heartbeat)
    parser.add_handler(MAV_MSG.GPS_RAW_INT, handle_gps)
    
    # Simulate incoming data (heartbeat)
    print("\nSimulating heartbeat message...")
    heartbeat_data = bytes([0xFD, 0x1C, 0x00, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00,
                           0x02, 0x00, 0x00, 0x00,  # type=2 (quad)
                           0x0C, 0x00, 0x00, 0x00,  # autopilot=12 (PX4)
                           0x84, 0x00, 0x00, 0x00,  # base_mode=132 (custom|auto)
                           0x04, 0x00, 0x00, 0x00,  # custom_mode=4 (auto)
                           0x04, 0x00, 0x00, 0x00])  # status=4 (active)
    
    messages = parser.parse(heartbeat_data)
    print(f"Parsed {len(messages)} messages")
    
    # Show statistics
    print(f"\nStatistics:")
    print(f"  Messages received: {parser.messages_received}")
    print(f"  Messages failed: {parser.messages_failed}")
    
    # Generate outbound message
    print("\nGenerating attitude message...")
    attitude_payload = struct.pack('<Iffff', 10000, 0.05, -0.1, 1.5, 0, 0, 0)
    print(f"  Payload size: {len(attitude_payload)} bytes")
    
    # Commands
    print("\nMAVLink Commands:")
    print(f"  RTL: {CommandLong.NAV_RETURN_TO_LAUNCH}")
    print(f"  TAKEOFF: {CommandLong.NAV_TAKEOFF}")
    print(f"  LAND: {CommandLong.NAV_LAND}")
    print(f"  ARM: {CommandLong.COMPONENT_ARM_DISARM}")


if __name__ == "__main__":
    demo_mavlink()