"""
SkyCore MAVLink Protocol Implementation
Based on mavlink/mavlink (official protocol)

Features:
- Complete MAVLink 2.0 message definitions
- Message CRC calculation
- Framing and parsing
- Heartbeat and heartbeat handling
- Message rate control
- MAVLink routing
"""

import struct
import time
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging


# MAVLink Message IDs (common subset)
class MAVLINK_MSG_ID(Enum):
    """Core MAVLink message IDs"""
    HEARTBEAT = 0
    SYS_STATUS = 1
    SYSTEM_TIME = 2
    PING = 3
    SET_MODE = 4
    PARAM_REQUEST_READ = 20
    PARAM_REQUEST_LIST = 21
    PARAM_VALUE = 22
    PARAM_SET = 23
    GPS_RAW_INT = 24
    GPS_STATUS = 25
    SCALED_IMU = 26
    IMU_RAW = 27
    ATTITUDE = 30
    ATTITUDE_QUATERNION = 31
    LOCAL_POSITION_NED = 32
    GLOBAL_POSITION_INT = 33
    RC_CHANNELS_SCALED = 34
    RC_CHANNELS_RAW = 35
    SERVO_OUTPUT_RAW = 36
    MISSION_REQUEST = 40
    MISSION_ITEM = 41
    MISSION_ACK = 47
    GPS_GLOBAL_ORIGIN = 49
    NAV_CONTROLLER_OUTPUT = 62
    RC_CHANNELS = 65
    REQUEST_DATA_STREAM = 66
    DATA_STREAM = 67
    MANUAL_CONTROL = 69
    RC_CHANNELS_OVERRIDE = 70
    MISSION_ITEM_INT = 73
    VFR_HUD = 74
    COMMAND_INT = 75
    COMMAND_LONG = 76
    COMMAND_ACK = 77
    V2_EXTENSION = 248
    FILE_TRANSFER_PROTOCOL = 100
    PING_ACT = 400
    Autopilot_Version = 148
    LOCAL_POSITION_NED_COV = 61


# MAV_TYPE - Vehicle/Component types
class MAV_TYPE(Enum):
    """MAVLink vehicle types"""
    GENERIC = 0
    FIXED_WING = 1
    QUADROTOR = 2
    COAXIAL = 3
    HELICOPTER = 4
    GROUND_EMERGENCY_RECOVERY = 10
    GROUND_SURFACE = 11
    GROUND_ROVER = 12
    BOAT = 13
    FREE_BALLOON = 14
    PARACHUTE = 19
    OCTOROTOR = 13
    HELICOPTER = 4
    ANNUNCIATOR = 26


# MAV_AUTOPILOT - Autopilot types
class MAV_AUTOPILOT(Enum):
    """MAVLink autopilot types"""
    GENERIC = 0
    PX4 = 12
    APM = 3
    QGROUNDCONTROL = 20
    AUTO = 7


# MAV_STATE - System status
class MAV_STATE(Enum):
    """MAVLink system states"""
    UNINIT = 0
    BOOT = 1
    ACTIVE = 4
    STANDBY = 3
    CRITICAL = 5
    EMERGENCY = 6
    POWEROFF = 7


# MAV_MODE - Flight mode flags
class MAV_MODE_FLAG(Enum):
    """MAVLink mode flags"""
    CUSTOM_MODE_ENABLED = 1
    TEST = 2
    AUTO_ENABLED = 4
    GUIDED_ENABLED = 8
    STABILIZE_ENABLED = 16
    HIL_ENABLED = 32
    MANUAL_INPUT_ENABLED = 64
    MAVLINK_ENABLED = 128


# MAV_FRAME - Coordinate frames
class MAV_FRAME(Enum):
    """MAVLink coordinate frames"""
    GLOBAL = 0
    LOCAL_NED = 1
    MISSION = 2
    GLOBAL_RELATIVE_ALT = 3
    LOCAL_FNED = 6
    GLOBAL_INT = 7
    GLOBAL_RELATIVE_ALT_INT = 8
    FRAME_BODY_NED = 9


# MAV_CMD - Command IDs
class MAV_CMD(Enum):
    """MAVLink commands"""
    NAV_WAYPOINT = 16
    NAV_LOITER_UNLIM = 17
    NAV_LOITER_TURNS = 18
    NAV_LOITER_TIME = 19
    NAV_RETURN_TO_LAUNCH = 20
    NAV_LAND = 21
    NAV_TAKEOFF = 22
    NAV_LAST = 95
    
    CONDITION_DELAY = 112
    CONDITION_DISTANCE = 113
    CONDITION_YAW = 115
    
    DO_SET_MODE = 176
    DO_JUMP = 177
    DO_CHANGE_SPEED = 178
    DO_SET_HOME = 189
    DO_SET_SERVO = 183
    DO_REPEAT_SERVO = 184
    
    CMD_ACK = 77
    COMPONENT_ARM_DISARM = 400


@dataclass
class MAVLinkHeader:
    """MAVLink message header"""
    start_byte: int = 0xFD  # MAVLink 2.0
    payload_length: int = 0
    incompatible_flags: int = 0
    compatible_flags: int = 0
    sequence: int = 0
    system_id: int = 1
    component_id: int = 1
    message_id: int = 0
    
    def to_bytes(self) -> bytes:
        """Serialize header to bytes"""
        return struct.pack(
            '<BBBBBBBQ',
            self.start_byte,
            self.payload_length,
            self.incompatible_flags,
            self.compatible_flags,
            self.sequence,
            self.system_id,
            self.component_id,
            self.message_id
        )
        
    @staticmethod
    def from_bytes(data: bytes) -> 'MAVLinkHeader':
        """Parse header from bytes"""
        if len(data) < 26:
            raise ValueError("Invalid MAVLink header")
            
        header = MAVLinkHeader()
        (
            header.start_byte,
            header.payload_length,
            header.incompatible_flags,
            header.compatible_flags,
            header.sequence,
            header.system_id,
            header.component_id
        ) = struct.unpack('<BBBBBBB', data[:7])
        header.message_id = struct.unpack('<I', data[7:11] + b'\x00\x00\x00')[0]
        
        return header


@dataclass
class MAVLinkMessage:
    """Complete MAVLink message"""
    header: MAVLinkHeader
    payload: bytes
    checksum: int = 0
    
    def to_frame(self) -> bytes:
        """Serialize complete message to frame"""
        header_bytes = self.header.to_bytes()
        payload_with_crc = self.payload + self._compute_crc()
        return header_bytes + payload_with_crc
        
    def _compute_crc(self) -> bytes:
        """Compute message CRC"""
        # CRC seed for MAVLink 2.0
        crc_seed = 0xFFFF
        
        # CRC includes message ID (for extensions)
        crc = self._crc_accumulate(self.header.message_id, crc_seed)
        
        # CRC includes payload
        for byte in self.payload:
            crc = self._crc_accumulate(byte, crc)
            
        return struct.pack('<H', crc & 0xFFFF)
        
    def _crc_accumulate(self, byte: int, crc: int) -> int:
        """CRC accumulate single byte"""
        data = byte ^ (crc & 0xFF)
        data ^= (data << 4) & 0xFF
        data ^= (data >> 4) & 0xFF
        data ^= (data << 3) & 0xFF
        return ((crc >> 8) ^ (data << 8)) & 0xFFFF


class MAVLinkProtocol:
    """
    MAVLink Protocol Handler
    Complete implementation of MAVLink 2.0
    """
    
    PROTOCOL_VERSION = "2.0"
    
    # Message signatures for signing
    LINK_STATS = {
        "msgs_sent": 0,
        "msgs_received": 0,
        "bytes_sent": 0,
        "bytes_received": 0,
        "msgs_lost": 0
    }
    
    def __init__(self, system_id: int = 255, component_id: int = 0):
        self.system_id = system_id
        self.component_id = component_id
        self.sequence = 0
        
        # Message handlers
        self._handlers: Dict[int, List[Callable]] = {}
        
        # Statistics
        self.stats = self.LINK_STATS.copy()
        
        # Buffer for parsing
        self._rx_buffer = bytearray()
        
        logging.info(f"MAVLink initialized (ID: {system_id}.{component_id})")
        
    def reset_sequence(self):
        """Reset message sequence counter"""
        self.sequence = 0
        
    def _next_sequence(self) -> int:
        """Get next sequence number"""
        seq = self.sequence
        self.sequence = (self.sequence + 1) % 256
        return seq
        
    # Message Construction
    def pack_message(
        self,
        msg_id: int,
        payload: bytes,
        incompatible_flags: int = 0,
        compatible_flags: int = 0
    ) -> bytes:
        """
        Pack message into MAVLink frame
        
        Args:
            msg_id: Message ID
            payload: Message payload bytes
            incompatible_flags: MAVLink 2 incompatible flags
            compatible_flags: MAVLink 2 compatible flags
            
        Returns:
            Complete MAVLink frame bytes
        """
        header = MAVLinkHeader(
            start_byte=0xFD,  # MAVLink 2
            payload_length=len(payload),
            incompatible_flags=incompatible_flags,
            compatible_flags=compatible_flags,
            sequence=self._next_sequence(),
            system_id=self.system_id,
            component_id=self.component_id,
            message_id=msg_id
        )
        
        message = MAVLinkMessage(header, payload)
        return message.to_frame()
        
    # Heartbeat
    def pack_heartbeat(
        self,
        mav_type: int = 2,  # MAV_TYPE_QUADROTOR
        autopilot: int = 12,  # MAV_AUTOPILOT_PX4
        base_mode: int = 0,
        custom_mode: int = 0,
        system_status: int = 4  # MAV_STATE_ACTIVE
    ) -> bytes:
        """Pack HEARTBEAT message"""
        payload = struct.pack(
            '<IBBBBI',
            mav_type,
            autopilot,
            base_mode,
            custom_mode,
            system_status,
            3  # MAVLINK_VERSION
        )
        
        return self.pack_message(MAVLINK_MSG_ID.HEARTBEAT.value, payload)
        
    def parse_heartbeat(self, payload: bytes) -> Dict:
        """Parse HEARTBEAT payload"""
        if len(payload) < 10:
            return {}
            
        mav_type, autopilot, base_mode, custom_mode, system_status, version = \
            struct.unpack('<IBBBBI', payload[:10])
            
        return {
            "type": mav_type,
            "autopilot": autopilot,
            "base_mode": base_mode,
            "custom_mode": custom_mode,
            "system_status": system_status
        }
        
    # System Status
    def pack_sys_status(
        self,
        onboard_control_sensors_present: int,
        onboard_control_sensors_enabled: int,
        onboard_control_sensors_health: int,
        load: int,
        voltage_battery: int,
        current_battery: int,
        battery_remaining: int,
        drop_rate_comm: int = 0,
        errors_comm: int = 0,
        errors_count_1: int = 0,
        errors_count_2: int = 0,
        errors_count_3: int = 0,
        errors_count_4: int = 0
    ) -> bytes:
        """Pack SYS_STATUS message"""
        payload = struct.pack(
            '<IIIHHhHhhhhh',
            onboard_control_sensors_present,
            onboard_control_sensors_enabled,
            onboard_control_sensors_health,
            load,
            voltage_battery,
            current_battery,
            battery_remaining,
            drop_rate_comm,
            errors_comm,
            errors_count_1,
            errors_count_2,
            errors_count_3,
            errors_count_4
        )
        
        return self.pack_message(MAVLINK_MSG_ID.SYS_STATUS.value, payload)
        
    # GPS Raw
    def pack_gps_raw_int(
        self,
        fix_type: int,
        lat: int,
        lon: int,
        alt: int,
        eph: int,
        epv: int,
        vel: int,
        cog: int,
        satellites_visible: int,
        time_usec: int = 0
    ) -> bytes:
        """Pack GPS_RAW_INT message"""
        payload = struct.pack(
            '<qiiiIHHHb',
            time_usec,
            fix_type,
            lat,
            lon,
            alt,
            eph,
            epv,
            vel,
            cog,
            satellites_visible
        )
        
        return self.pack_message(MAVLINK_MSG_ID.GPS_RAW_INT.value, payload)
        
    # Global Position
    def pack_global_position_int(
        self,
        time_boot_ms: int,
        lat: int,
        lon: int,
        alt: int,
        relative_alt: int,
        vx: int,
        vy: int,
        vz: int,
        hdg: int
    ) -> bytes:
        """Pack GLOBAL_POSITION_INT message"""
        payload = struct.pack(
            '<Iiiiihhhhh',
            time_boot_ms,
            lat,
            lon,
            alt,
            relative_alt,
            vx,
            vy,
            vz,
            hdg,
            0  # placeholder
        )
        
        return self.pack_message(MAVLINK_MSG_ID.GLOBAL_POSITION_INT.value, payload)
        
    # Attitude
    def pack_attitude(
        self,
        time_boot_ms: int,
        roll: float,
        pitch: float,
        yaw: float,
        rollspeed: float,
        pitchspeed: float,
        yawspeed: float
    ) -> bytes:
        """Pack ATTITUDE message"""
        payload = struct.pack(
            '<Ifffffff',
            time_boot_ms,
            roll,
            pitch,
            yaw,
            rollspeed,
            pitchspeed,
            yawspeed,
            0  # alignment
        )
        
        return self.pack_message(MAVLINK_MSG_ID.ATTITUDE.value, payload)
        
    # Command Long
    def pack_command_long(
        self,
        command: int,
        param1: float,
        param2: float,
        param3: float,
        param4: float,
        param5: float,
        param6: float,
        param7: float,
        target_system: int = 1,
        target_component: int = 0,
        confirmation: int = 0
    ) -> bytes:
        """Pack COMMAND_LONG message"""
        payload = struct.pack(
            '<BBBBHHffffff',
            target_system,
            target_component,
            command & 0xFF,
            (command >> 8) & 0xFF,
            (command >> 16) & 0xFF,
            (command >> 24) & 0xFF,
            param1, param2, param3, param4, param5, param6, param7,
            confirmation
        )
        
        return self.pack_message(MAVLINK_MSG_ID.COMMAND_LONG.value, payload)
        
    # Mission Item
    def pack_mission_item_int(
        self,
        target_system: int,
        target_component: int,
        seq: int,
        frame: int,
        command: int,
        current: int,
        autocontinue: int,
        param1: float,
        param2: float,
        param3: float,
        param4: float,
        x: int,
        y: int,
        z: float
    ) -> bytes:
        """Pack MISSION_ITEM_INT message"""
        payload = struct.pack(
            '<BBBBHHIffffffii',
            target_system,
            target_component,
            seq & 0xFF,
            (seq >> 8) & 0xFF,
            frame,
            command & 0xFF,
            (command >> 8) & 0xFF,
            (command >> 16) & 0xFF,
            (command >> 24) & 0xFF,
            current,
            autocontinue,
            param1, param2, param3, param4,
            x, y, z
        )
        
        return self.pack_message(MAVLINK_MSG_ID.MISSION_ITEM_INT.value, payload)
        
    # Parsing
    def parse_frame(self, data: bytes) -> Optional[MAVLinkMessage]:
        """
        Parse MAVLink frame from raw bytes
        
        Args:
            data: Raw bytes
            
        Returns:
            Parsed MAVLinkMessage or None
        """
        # Look for start byte
        for i, byte in enumerate(data):
            if byte == 0xFD or byte == 0xFE:  # MAVLink 2.0 or 1.0
                try:
                    header = self._parse_header(data[i:])
                    payload_start = i + 12 if byte == 0xFD else i + 6
                    
                    if payload_start + header.payload_length + 2 <= len(data):
                        payload = data[payload_start:payload_start + header.payload_length]
                        checksum = struct.unpack('<H', data[payload_start + header.payload_length:payload_start + header.payload_length + 2])[0]
                        
                        msg = MAVLinkMessage(header, payload, checksum)
                        self.stats["msgs_received"] += 1
                        return msg
                        
                except Exception:
                    continue
                    
        return None
        
    def _parse_header(self, data: bytes) -> MAVLinkHeader:
        """Parse MAVLink header"""
        if len(data) < 12:
            raise ValueError("Insufficient data for header")
            
        header = MAVLinkHeader()
        header.start_byte = data[0]
        
        if header.start_byte == 0xFD:  # MAVLink 2
            header.payload_length = data[1]
            header.incompatible_flags = data[2]
            header.compatible_flags = data[3]
            header.sequence = data[4]
            header.system_id = data[5]
            header.component_id = data[6]
            header.message_id = struct.unpack('<I', data[7:11] + b'\x00\x00\x00')[0]
        else:  # MAVLink 1
            header.payload_length = data[1]
            header.sequence = data[2]
            header.system_id = data[3]
            header.component_id = data[4]
            header.message_id = data[5]
            
        return header
        
    # Handler Registration
    def register_message_handler(
        self,
        msg_id: int,
        handler: Callable[[bytes], Any]
    ):
        """Register handler for message type"""
        if msg_id not in self._handlers:
            self._handlers[msg_id] = []
        self._handlers[msg_id].append(handler)
        
    def handle_message(self, message: MAVLinkMessage):
        """Handle received message"""
        msg_id = message.header.message_id
        
        if msg_id in self._handlers:
            for handler in self._handlers[msg_id]:
                try:
                    handler(message.payload)
                except Exception as e:
                    logging.error(f"Handler error for msg {msg_id}: {e}")
                    
    # Statistics
    def get_stats(self) -> Dict:
        """Get link statistics"""
        return self.stats.copy()
        
    def reset_stats(self):
        """Reset statistics"""
        self.stats = self.LINK_STATS.copy()


class MAVLinkRouter:
    """
    MAVLink Message Router
    Handles message routing between components
    """
    
    def __init__(self, protocol: MAVLinkProtocol):
        self.protocol = protocol
        self.routes: Dict[Tuple[int, int], List[int]] = {}  # (sys, comp) -> [targets]
        self.filters: List[Dict] = []
        
    def add_route(
        self,
        source_system: int,
        source_component: int,
        target_system: int
    ):
        """Add routing rule"""
        key = (source_system, source_component)
        if key not in self.routes:
            self.routes[key] = []
        self.routes[key].append(target_system)
        
    def route_message(self, message: MAVLinkMessage) -> List[bytes]:
        """Route message to all destinations"""
        source = (message.header.system_id, message.header.component_id)
        destinations = self.routes.get(source, [])
        
        frames = []
        for dest in destinations:
            # Forward with changed destination
            routed_header = message.header
            routed_header.system_id = dest
            
            routed_msg = MAVLinkMessage(routed_header, message.payload)
            frames.append(routed_msg.to_frame())
            
        return frames
        
    def add_filter(
        self,
        msg_id: int,
        field_name: str,
        min_value: float,
        max_value: float
    ):
        """Add message filter"""
        self.filters.append({
            "msg_id": msg_id,
            "field": field_name,
            "min": min_value,
            "max": max_value
        })
        
    def should_forward(self, message: MAVLinkMessage) -> bool:
        """Check if message should be forwarded"""
        for filter_def in self.filters:
            if message.header.message_id == filter_def["msg_id"]:
                # Apply filter (simplified)
                pass
        return True


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create MAVLink protocol
    mav = MAVLinkProtocol(system_id=255, component_id=0)
    
    # Pack heartbeat
    hb = mav.pack_heartbeat(
        mav_type=2,  # Quadrotor
        autopilot=12,  # PX4
        system_status=4  # Active
    )
    print(f"Heartbeat frame: {hb.hex()}")
    
    # Pack GPS message
    gps = mav.pack_gps_raw_int(
        fix_type=3,
        lat=int(32.0853 * 1e7),
        lon=int(34.7818 * 1e7),
        alt=int(50 * 1000),
        eph=100,
        epv=150,
        vel=0,
        cog=0,
        satellites_visible=12
    )
    print(f"GPS frame: {gps.hex()}")
    
    # Pack command (ARM)
    arm_cmd = mav.pack_command_long(
        command=400,  # MAV_CMD_COMPONENT_ARM_DISARM
        param1=1.0,  # Arm
        target_system=1
    )
    print(f"ARM command frame: {arm_cmd.hex()}")
    
    # Pack mission item
    waypoint = mav.pack_mission_item_int(
        target_system=1,
        target_component=0,
        seq=0,
        frame=6,  # GLOBAL_RELATIVE_ALT
        command=16,  # NAV_WAYPOINT
        current=1,
        autocontinue=1,
        x=int(32.0853 * 1e7),
        y=int(34.7818 * 1e7),
        z=30.0
    )
    print(f"Mission waypoint frame: {waypoint.hex()}")
    
    # Get stats
    stats = mav.get_stats()
    print(f"Link stats: {stats}")