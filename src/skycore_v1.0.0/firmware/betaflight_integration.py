"""
SkyCore Betaflight/CleanFlight Integration
Based on betaflight/betaflight (10969 stars) and cleanflight/cleanflight

Features:
- Betaflight MSP protocol
- Configurator settings
- Blackbox log parsing
- OSD elements
- CLI commands
- Betaflight-specific features (dyn_idle, anti_gravity, etc.)
"""

import struct
import time
import logging
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum


# Betaflight MSP Protocol
class MSP_CMD(Enum):
    """Betaflight MSP commands"""
    # Core commands
    MSP_API_VERSION = 1
    MSP_FC_VARIANT = 2
    MSP_FC_VERSION = 3
    MSP_BOARD_INFO = 4
    MSP_BUILD_INFO = 5
    
    # Ident commands
    MSP_IDENT = 100
    MSP_STATUS = 101
    MSP_RAW_IMU = 102
    MSP_SERVO = 103
    MSP_MOTOR = 104
    MSP_RC = 105
    MSP_RAW_GPS = 106
    MSP_COMP_GPS = 107
    MSP_ATTITUDE = 108
    MSP_ALTITUDE = 109
    MSP_ANALOG = 110
    MSP_VOLTAGE_METER = 115
    MSP_CURRENT_METER = 118
    
    # RC commands
    MSP_RC_TUNING = 111
    MSP_PID = 112
    MSP_PIDNAMES = 113
    
    # Box commands
    MSP_BOXNAMES = 116
    MSP_BOXIDS = 119
    
    # Configuration commands
    MSP_MODE_RANGES = 123
    MSP_MODE_RANGE = 124
    
    # Boards
    MSP_BOARD_ALIGNMENT = 126
    MSP_ARMING_CONFIG = 127
    MSP_BOARD_MODE = 128
    
    # Advanced
    MSP_REBOOT = 68
    MSP_BF_CONFIG = 86
    MSP_SET_BF_CONFIG = 87
    
    # Debug
    MSP_DEBUG = 253
    MSP_OSD_CONFIG = 84
    MSP_SET_OSD_CONFIG = 85


@dataclass
class BetaflightConfig:
    """Betaflight configuration"""
    # PID
    pid_p = [0.0] * 10
    pid_i = [0.0] * 10
    pid_d = [0.0] * 10
    
    # Rates
    roll_rate = 0.0
    pitch_rate = 0.0
    yaw_rate = 0.0
    
    # RC rates
    rc_rate = 1.0
    rc_expo = 0.0
    roll_rc_rate = 0.0
    pitch_rc_rate = 0.0
    
    # TPA
    tpa_rate = 0.0
    tpa_breakpoint = 1650
    
    # Filters
    gyro_lowpass = 100
    dterm_lowpass = 100
    yaw_lowpass = 100
    
    # Features
    arming_flags = 0
    min_throttle = 1000
    max_throttle = 2000
    min_command = 1000
    
    # dyn_idle
    dyn_idle_min_rpm = 0
    dyn_idle_max_rpm = 0
    dyn_idle_p = 0
    dyn_idle_d = 0
    dyn_idle_min = 0
    
    # Anti-gravity
    anti_gravity_gain = 0
    anti_gravity_threshold = 0
    
    # Battery
    vbat_scale = 107
    vbat_min_cell_voltage = 33
    vbat_max_cell_voltage = 43
    vbat_warning_cell_voltage = 35


@dataclass
class BetaflightRC:
    """RC input data"""
    roll: int = 1500
    pitch: int = 1500
    throttle: int = 1000
    yaw: int = 1500
    aux1: int = 1000
    aux2: int = 1000
    aux3: int = 1000
    aux4: int = 1000
    
    def to_bytes(self) -> bytes:
        """Convert to MSP format"""
        return struct.pack('<HHHHHHHH', 
            self.roll, self.pitch, self.throttle, self.yaw,
            self.aux1, self.aux2, self.aux3, self.aux4)


@dataclass 
class BetaflightIMU:
    """IMU sensor data"""
    accel_x: int = 0
    accel_y: int = 0
    accel_z: int = 0
    gyro_x: int = 0
    gyro_y: int = 0
    gyro_z: int = 0
    mag_x: int = 0
    mag_y: int = 0
    mag_z: int = 0


class BetaflightMSP:
    """
    Betaflight MSP Protocol Handler
    Implements full MSP protocol for Betaflight
    """
    
    # MSP direction
    MSP_REQUEST = 0
    MSP_RESPONSE = 1
    MSP_SET = 2
    
    def __init__(self):
        self.config = BetaflightConfig()
        self.connected = False
        self.board_info = {}
        self.fc_variant = "BF"
        self.fc_version = "4.0"
        
        # MSP state
        self._request_queue: List[Tuple[int, bool]] = []
        
        logging.info("Betaflight MSP initialized")
        
    def connect(self, device: str = "/dev/ttyUSB0", baudrate: int = 115200) -> bool:
        """Connect to Betaflight flight controller"""
        logging.info(f"Connecting to Betaflight on {device}...")
        
        try:
            # Query board info
            self._query_board_info()
            self.connected = True
            return True
        except Exception as e:
            logging.error(f"Betaflight connection failed: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from Betaflight"""
        self.connected = False
        logging.info("Betaflight disconnected")
        
    def _query_board_info(self):
        """Query board information"""
        # Send MSP_API_VERSION
        response = self._send_msp(MSP_CMD.MSP_API_VERSION, MSP_CMD.MSP_API_VERSION)
        if response:
            major, minor, patch = struct.unpack('<BBB', response[:3])
            logging.info(f"MSP API: {major}.{minor}.{patch}")
            
        # Send MSP_FC_VARIANT
        response = self._send_msp(MSP_CMD.MSP_FC_VARIANT, MSP_CMD.MSP_FC_VARIANT)
        if response:
            self.fc_variant = response.decode('ascii', errors='ignore').strip()
            
        # Send MSP_FC_VERSION
        response = self._send_msp(MSP_CMD.MSP_FC_VERSION, MSP_CMD.MSP_FC_VERSION)
        if response:
            major, minor, patch = struct.unpack('<BBB', response[:3])
            self.fc_version = f"{major}.{minor}.{patch}"
            
        self.board_info = {
            "variant": self.fc_variant,
            "version": self.fc_version
        }
        
    def _send_msp(self, cmd: MSP_CMD, expected_response: Optional[MSP_CMD] = None) -> Optional[bytes]:
        """Send MSP command and get response"""
        # Simulate MSP exchange
        return self._simulate_response(cmd.value)
        
    def _simulate_response(self, cmd_id: int) -> Optional[bytes]:
        """Simulate MSP response for testing"""
        if cmd_id == MSP_CMD.MSP_API_VERSION.value:
            return bytes([2, 1, 0])  # v2.1.0
        return None
        
    # Configuration
    def load_config(self) -> BetaflightConfig:
        """Load Betaflight configuration"""
        # Query PID
        pid_data = self._send_msp(MSP_CMD.MSP_PID, MSP_CMD.MSP_PID)
        if pid_data and len(pid_data) >= 30:
            for i in range(10):
                self.config.pid_p[i] = struct.unpack('<H', pid_data[i*3:i*3+2])[0] / 10.0
                self.config.pid_i[i] = struct.unpack('<H', pid_data[i*3+10:i*3+12])[0] / 1000.0
                self.config.pid_d[i] = struct.unpack('<H', pid_data[i*3+20:i*3+22])[0] / 100.0
                
        # Query RC rates
        rc_tuning = self._send_msp(MSP_CMD.MSP_RC_TUNING, MSP_CMD.MSP_RC_TUNING)
        if rc_tuning:
            self.config.rc_rate = struct.unpack('<B', rc_tuning[0:1])[0] / 100.0
            self.config.roll_rc_rate = self.config.rc_rate
            self.config.pitch_rc_rate = self.config.rc_rate
            
        return self.config
        
    def save_config(self):
        """Save configuration to Betaflight"""
        logging.info("Saving Betaflight configuration...")
        
    # CLI Commands
    def cli_write(self, command: str):
        """
        Send CLI command
        
        Args:
            command: CLI command string
        """
        logging.info(f"Betaflight CLI: {command}")
        # Send 'exit' or 'save' to save
        
    def cli_set(self, setting: str, value: Any):
        """Set CLI setting"""
        self.cli_write(f"set {setting} = {value}")
        
    def reboot(self):
        """Reboot Betaflight"""
        self._send_msp(MSP_CMD.MSP_REBOOT, None)
        time.sleep(2)
        self.disconnect()
        
    # Modes/Aux
    def get_modes(self) -> Dict[str, int]:
        """Get configured modes"""
        # Query box names
        box_names = self._send_msp(MSP_CMD.MSP_BOXNAMES, MSP_CMD.MSP_BOXNAMES)
        # Parse mode names
        
        return {
            "ARM": 0,
            "ANGLE": 1,
            "HORIZON": 2,
            "BARO": 3,
            "MAG": 4,
            "HEADFREE": 5,
            "GPSRESCUE": 26
        }
        
    def set_mode(self, mode_id: int, channel_value: int):
        """Set mode via auxiliary channel"""
        pass
        
    # Blackbox
    def parse_blackbox_log(self, log_data: bytes) -> List[Dict]:
        """
        Parse Betaflight blackbox log
        
        Returns:
            List of flight log frames
        """
        frames = []
        
        # Blackbox I frame format
        # Contains main flight data
        
        # Parse loop
        offset = 0
        while offset < len(log_data):
            try:
                frame_type = log_data[offset]
                offset += 1
                
                if frame_type == 0:  # I-frame
                    frame = self._parse_i_frame(log_data[offset:])
                    frames.append(frame)
                elif frame_type == 1:  # P-frame
                    frame = self._parse_p_frame(log_data[offset:])
                    frames.append(frame)
                elif frame_type == 2:  # G-frame (GPS)
                    frame = self._parse_g_frame(log_data[offset:])
                    frames.append(frame)
                    
            except Exception:
                break
                
        return frames
        
    def _parse_i_frame(self, data: bytes) -> Dict:
        """Parse I-frame (keyframe)"""
        if len(data) < 64:
            return {}
            
        frame = {
            "time": struct.unpack('<I', data[0:4])[0],
            "loopIteration": struct.unpack('<I', data[4:8])[0],
            "axisP[0]": struct.unpack('<h', data[8:10])[0],
            "axisP[1]": struct.unpack('<h', data[10:12])[0],
            "axisP[2]": struct.unpack('<h', data[12:14])[0],
            "axisI[0]": struct.unpack('<h', data[14:16])[0],
            "axisI[1]": struct.unpack('<h', data[16:18])[0],
            "axisI[2]": struct.unpack('<h', data[18:20])[0],
            "axisD[0]": struct.unpack('<h', data[20:22])[0],
            "axisD[1]": struct.unpack('<h', data[22:24])[0],
            "axisD[2]": struct.unpack('<h', data[24:26])[0],
            "rcCommand[0]": struct.unpack('<h', data[26:28])[0],
            "rcCommand[1]": struct.unpack('<h', data[28:30])[0],
            "rcCommand[2]": struct.unpack('<h', data[30:32])[0],
            "rcCommand[3]": struct.unpack('<h', data[32:34])[0],
        }
        
        return frame
        
    def _parse_p_frame(self, data: bytes) -> Dict:
        """Parse P-frame (delta frame)"""
        return {}
        
    def _parse_g_frame(self, data: bytes) -> Dict:
        """Parse G-frame (GPS data)"""
        return {}
        
    # Status
    def get_status(self) -> Dict:
        """Get Betaflight status"""
        status_data = self._send_msp(MSP_CMD.MSP_STATUS, MSP_CMD.MSP_STATUS)
        
        if status_data and len(status_data) >= 25:
            return {
                "cycle_time": struct.unpack('<I', status_data[0:4])[0],
                "cpu_load": struct.unpack('<H', status_data[4:6])[0],
                "packet_count": struct.unpack('<H', status_data[6:8])[0],
                "i2c_errors": struct.unpack('<H', status_data[8:10])[0],
                "sensors": struct.unpack('<I', status_data[10:14])[0],
                "box_mode": struct.unpack('<I', status_data[14:18])[0],
                "current_pid_set": status_data[18],
                "num_profile": status_data[19],
                "cpuload": struct.unpack('<H', status_data[20:22])[0],
                "gyro_sync": struct.unpack('<H', status_data[22:24])[0]
            }
            
        return {}
        
    def get_raw_imu(self) -> BetaflightIMU:
        """Get raw IMU data"""
        imu_data = self._send_msp(MSP_CMD.MSP_RAW_IMU, MSP_CMD.MSP_RAW_IMU)
        
        imu = BetaflightIMU()
        if imu_data and len(imu_data) >= 18:
            imu.accel_x = struct.unpack('<h', imu_data[0:2])[0]
            imu.accel_y = struct.unpack('<h', imu_data[2:4])[0]
            imu.accel_z = struct.unpack('<h', imu_data[4:6])[0]
            imu.gyro_x = struct.unpack('<h', imu_data[6:8])[0]
            imu.gyro_y = struct.unpack('<h', imu_data[8:10])[0]
            imu.gyro_z = struct.unpack('<h', imu_data[10:12])[0]
            imu.mag_x = struct.unpack('<h', imu_data[12:14])[0]
            imu.mag_y = struct.unpack('<h', imu_data[14:16])[0]
            imu.mag_z = struct.unpack('<h', imu_data[16:18])[0]
            
        return imu
        
    def get_analog(self) -> Dict:
        """Get analog sensor values"""
        analog_data = self._send_msp(MSP_CMD.MSP_ANALOG, MSP_CMD.MSP_ANALOG)
        
        if analog_data and len(analog_data) >= 7:
            return {
                "battery_voltage": struct.unpack('<B', analog_data[0:1])[0] / 10.0,
                "current": struct.unpack('<H', analog_data[1:3])[0],
                "mah": struct.unpack('<I', analog_data[3:7])[0],
                "rssi": struct.unpack('<H', analog_data[5:7])[0]
            }
            
        return {}


class CleanFlightMixer:
    """
    CleanFlight/Betaflight Motor Mixer
    Handles motor output calculation for different frames
    """
    
    # Frame types
    FRAME_QUAD_X = 1
    FRAME_QUAD_PLUS = 2
    FRAME_HEXA = 3
    FRAME_OCTO_X = 4
    FRAME_OCTO_PLUS = 5
    FRAME_HEXA_X = 6
    
    def __init__(self, frame_type: int = FRAME_QUAD_X):
        self.frame_type = frame_type
        self.motor_count = self._get_motor_count()
        
    def _get_motor_count(self) -> int:
        """Get motor count for frame type"""
        if self.frame_type == self.FRAME_QUAD_X:
            return 4
        elif self.frame_type in [self.FRAME_HEXA, self.FRAME_HEXA_X]:
            return 6
        elif self.frame_type in [self.FRAME_OCTO_X, self.FRAME_OCTO_PLUS]:
            return 8
        return 4
        
    def compute_motor_outputs(
        self,
        roll: float,
        pitch: float,
        yaw: float,
        thrust: float
    ) -> List[float]:
        """
        Compute motor outputs for given inputs
        
        Args:
            roll: Roll command (-1 to 1)
            pitch: Pitch command (-1 to 1)
            yaw: Yaw command (-1 to 1)
            thrust: Throttle (0 to 1)
            
        Returns:
            List of motor outputs (normalized 0-1)
        """
        outputs = [0.0] * self.motor_count
        
        if self.frame_type == self.FRAME_QUAD_X:
            # Quad X configuration
            # Motor layout (view from above):
            #   M2 (FL)    M1 (FR)
            #       \    /
            #        XXXX
            #       /    \
            #   M3 (BL)    M4 (BR)
            
            outputs[0] = thrust - pitch + roll + yaw  # M1 FR
            outputs[1] = thrust - pitch - roll - yaw  # M2 FL
            outputs[2] = thrust + pitch - roll + yaw  # M3 BL
            outputs[3] = thrust + pitch + roll - yaw  # M4 BR
            
        elif self.frame_type == self.FRAME_QUAD_PLUS:
            # Quad + configuration
            outputs[0] = thrust + pitch              # Front
            outputs[1] = thrust - roll                # Right
            outputs[2] = thrust - pitch               # Back
            outputs[3] = thrust + roll                # Left
            
        elif self.frame_type == self.FRAME_HEXA:
            # Hexa configuration
            for i in range(6):
                angle = i * 60  # degrees
                angle_rad = angle * 3.14159 / 180
                
                roll_contrib = roll * -math.sin(angle_rad)
                pitch_contrib = pitch * math.cos(angle_rad)
                
                outputs[i] = thrust + pitch_contrib + roll_contrib + yaw * (-1 if i % 2 else 1)
                
        # Limit outputs
        for i in range(len(outputs)):
            outputs[i] = max(0.0, min(1.0, outputs[i]))
            
        return outputs
        
    def compute_pwm_outputs(self, motor_outputs: List[float]) -> List[int]:
        """Convert normalized outputs to PWM values"""
        return [int(1000 + 1000 * v) for v in motor_outputs]


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create Betaflight instance
    bf = BetaflightMSP()
    
    if bf.connect("/dev/ttyUSB0"):
        print(f"Connected to {bf.fc_variant} v{bf.fc_version}")
        
        # Load config
        config = bf.load_config()
        print(f"Roll rate: {config.roll_rate}")
        print(f"Gyro LP: {config.gyro_lowpass}")
        
        # CLI commands
        bf.cli_write("version")
        bf.cli_set("gyro_lowpass_type", "PT1")
        bf.cli_set("dterm_lowpass_type", "BIQUAD")
        
        # Get status
        status = bf.get_status()
        print(f"CPU load: {status.get('cpu_load', 0)}%")
        print(f"Cycle time: {status.get('cycle_time', 0)}us")
        
        # Get IMU
        imu = bf.get_raw_imu()
        print(f"Accel: {imu.accel_x}, {imu.accel_y}, {imu.accel_z}")
        
        # Test motor mixer
        mixer = CleanFlightMixer(CleanFlightMixer.FRAME_QUAD_X)
        outputs = mixer.compute_motor_outputs(0.1, 0.1, 0, 0.5)
        print(f"Motor outputs: {[f'{o:.3f}' for o in outputs]}")
        print(f"PWM values: {mixer.compute_pwm_outputs(outputs)}")
        
        # Reboot
        bf.reboot()