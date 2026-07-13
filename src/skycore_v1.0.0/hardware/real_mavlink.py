"""
SkyCore Real Hardware Connection
Real MAVLink serial connection to real drones
"""

import time
import logging
from typing import Dict, List, Optional, Tuple, Any

# Real imports
from pymavlink import mavutil
from pymavlink.dialects.v20 import ardupilotmega

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealMAVLinkConnection:
    """
    Real MAVLink connection using pymavlink
    Connects to actual serial ports
    """
    
    def __init__(self, connection_string: str = None):
        self.master = None
        self.connection_string = connection_string or "tcp:localhost:5760"
        self.last_heartbeat = 0
        self.target_system = 1
        self.target_component = 1
        
    def connect(self, connection_string: str = None) -> bool:
        """
        Connect to MAVLink device
        
        Args:
            connection_string: Connection string like:
                - serial:/dev/ttyUSB0:921600
                - tcp:localhost:5760
                - udp:localhost:14550
                
        Returns:
            True if connected
        """
        if connection_string:
            self.connection_string = connection_string
            
        try:
            logger.info(f"Connecting to: {self.connection_string}")
            self.master = mavutil.mavlink_connection(
                self.connection_string,
                baud=921600,
                dialect='ardupilotmega'
            )
            
            # Wait for heartbeat
            logger.info("Waiting for heartbeat...")
            self.master.wait_heartbeat(timeout=10)
            
            logger.info(f"Connected to system {self.master.target_system}")
            self.target_system = self.master.target_system
            self.target_component = self.master.target_component
            
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from device"""
        if self.master:
            self.master.close()
            self.master = None
            logger.info("Disconnected")
            
    def arm(self) -> bool:
        """Arm the vehicle"""
        try:
            self.master.arducopter_arm()
            logger.info("Arm command sent")
            return True
        except Exception as e:
            logger.error(f"Arm failed: {e}")
            return False
            
    def disarm(self) -> bool:
        """Disarm the vehicle"""
        try:
            self.master.arducopter_disarm()
            logger.info("Disarm command sent")
            return True
        except Exception as e:
            logger.error(f"Disarm failed: {e}")
            return False
            
    def set_mode(self, mode: str) -> bool:
        """
        Set flight mode
        
        Args:
            mode: Mode name (STABILIZE, ALT_HOLD, LOITER, etc.)
        """
        try:
            mode_id = self.master.mode_mapping().get(mode.upper())
            if mode_id is None:
                logger.error(f"Unknown mode: {mode}")
                return False
                
            self.master.set_mode(mode_id)
            logger.info(f"Mode set to: {mode}")
            return True
            
        except Exception as e:
            logger.error(f"Mode change failed: {e}")
            return False
            
    def command_long(
        self,
        command: int,
        param1: float = 0,
        param2: float = 0,
        param3: float = 0,
        param4: float = 0,
        param5: float = 0,
        param6: float = 0,
        param7: float = 0
    ) -> bool:
        """
        Send MAVLink command_long
        
        Args:
            command: MAV_CMD command ID
            param1-7: Command parameters
        """
        try:
            self.master.mav.command_long_send(
                self.target_system,
                self.target_component,
                command,
                0,  # confirmation
                param1, param2, param3, param4, param5, param6, param7
            )
            return True
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return False
            
    def takeoff(self, altitude: float = 10.0) -> bool:
        """Command takeoff"""
        return self.command_long(
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0, 0, 0, 0,  # param 1-4
            0, 0, altitude  # lat, lon, alt
        )
        
    def land(self, lat: float = 0, lon: float = 0, alt: float = 0) -> bool:
        """Command landing"""
        return self.command_long(
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0,  # precision land
            0, 0, 0,  # params 2-4
            lat, lon, alt
        )
        
    def set_position_target(self, lat: float, lon: float, alt: float, yaw: float = 0):
        """
        Set position target for guided mode
        """
        self.master.mav.set_position_target_local_ned_send(
            0,  # time boot ms
            self.target_system,
            self.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
            0b110111111000,  # type mask (positions only)
            lat, lon, alt,  # x, y, z positions
            0, 0, 0,  # x, y, z velocity
            0, 0, 0,  # x, y, z acceleration
            yaw, 0  # yaw, yaw rate
        )
        
    def set_roi(self, lat: float, lon: float, alt: float):
        """Set region of interest (camera target)"""
        self.master.mav.command_long_send(
            self.target_system,
            self.target_component,
            mavutil.mavlink.MAV_CMD_NAV_ROI,
            0, 0, 0, 0, 0,
            lat, lon, alt
        )
        
    def get_telemetry(self) -> Dict[str, Any]:
        """
        Get current telemetry data
        
        Returns:
            Dictionary with position, attitude, battery, etc.
        """
        if not self.master:
            return {}
            
        telemetry = {
            "timestamp": time.time(),
            "connected": True
        }
        
        # Try to get messages without blocking
        msg = self.master.recv_msg()
        
        if msg:
            if msg.get_type() == 'GLOBAL_POSITION_INT':
                telemetry['lat'] = msg.lat / 1e7
                telemetry['lon'] = msg.lon / 1e7
                telemetry['alt'] = msg.alt / 1000
                telemetry['relative_alt'] = msg.relative_alt / 1000
                telemetry['vx'] = msg.vx / 100
                telemetry['vy'] = msg.vy / 100
                telemetry['vz'] = msg.vz / 100
                telemetry['hdg'] = msg.hdg / 100
                
            elif msg.get_type() == 'ATTITUDE':
                telemetry['roll'] = msg.roll * 180 / 3.14159
                telemetry['pitch'] = msg.pitch * 180 / 3.14159
                telemetry['yaw'] = msg.yaw * 180 / 3.14159
                telemetry['rollspeed'] = msg.rollspeed
                telemetry['pitchspeed'] = msg.pitchspeed
                telemetry['yawspeed'] = msg.yawspeed
                
            elif msg.get_type() == 'SYS_STATUS':
                telemetry['battery_voltage'] = msg.voltage_battery / 1000
                telemetry['battery_current'] = msg.current_battery / 100
                telemetry['battery_remaining'] = msg.battery_remaining
                
            elif msg.get_type() == 'GPS_RAW_INT':
                telemetry['gps_fix'] = msg.fix_type
                telemetry['gps_sats'] = msg.satellites_visible
                telemetry['gps_hdop'] = msg.eph / 100
                
            elif msg.get_type() == 'HEARTBEAT':
                telemetry['armed'] = msg.base_mode & 0x80
                telemetry['custom_mode'] = msg.custom_mode
                
        return telemetry
        
    def send_heartbeat(self):
        """Send heartbeat"""
        if self.master:
            self.master.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_QUADROTOR,
                mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                0,  # base mode
                0,  # custom mode
                mavutil.mavlink.MAV_STATE_ACTIVE
            )
            
    def upload_mission(self, waypoints: List[Dict]) -> bool:
        """
        Upload mission to vehicle
        
        Args:
            waypoints: List of waypoint dicts with lat, lon, alt
        """
        try:
            # Clear existing mission
            self.command_long(mavutil.mavlink.MAV_CMD_MISSION_CLEAR_ALL)
            time.sleep(0.5)
            
            # Send mission count
            self.master.mav.mission_count_send(
                self.target_system,
                self.target_component,
                len(waypoints)
            )
            
            # Wait for request
            for _ in range(len(waypoints) + 5):
                msg = self.master.recv_match(type='MISSION_REQUEST', blocking=True, timeout=5)
                if msg:
                    seq = msg.seq
                    
                    # Send waypoint
                    wp = waypoints[seq]
                    self.master.mav.mission_item_send(
                        self.target_system,
                        self.target_component,
                        seq,
                        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                        mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                        0, 1,  # current, autocontinue
                        0, 0, 0, 0,  # params
                        wp['lat'],
                        wp['lon'],
                        wp['alt']
                    )
                    
            logger.info(f"Uploaded {len(waypoints)} waypoints")
            return True
            
        except Exception as e:
            logger.error(f"Mission upload failed: {e}")
            return False
            
    def download_mission(self) -> List[Dict]:
        """
        Download mission from vehicle
        """
        try:
            # Request mission items
            self.command_long(mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, 0, 0, 0, 0, 0, 0, 0, 43)
            
            # Wait for mission
            mission_items = []
            max_items = 50
            
            for _ in range(max_items):
                msg = self.master.recv_match(
                    type='MISSION_ITEM_INT',
                    blocking=True,
                    timeout=5
                )
                if msg:
                    mission_items.append({
                        'seq': msg.seq,
                        'frame': msg.frame,
                        'command': msg.command,
                        'lat': msg.x / 1e7,
                        'lon': msg.y / 1e7,
                        'alt': msg.z
                    })
                    
                    if msg.seq == 0:
                        break
                        
            return mission_items
            
        except Exception as e:
            logger.error(f"Mission download failed: {e}")
            return []
            
    def set_param(self, name: str, value: float) -> bool:
        """Set parameter"""
        try:
            self.master.param_set_send(name, value)
            logger.info(f"Set {name} = {value}")
            return True
        except Exception as e:
            logger.error(f"Param set failed: {e}")
            return False
            
    def get_param(self, name: str) -> Optional[float]:
        """Get parameter"""
        try:
            value = self.master.param_fetch_one(name)
            return value
        except:
            return None
            
    def reboot(self):
        """Reboot vehicle"""
        self.command_long(mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN)


# Example usage
if __name__ == "__main__":
    import sys
    
    # Connection string from command line
    conn_str = sys.argv[1] if len(sys.argv) > 1 else "tcp:localhost:5760"
    
    print(f"Connecting to: {conn_str}")
    
    # Create connection
    mav = RealMAVLinkConnection(conn_str)
    
    if mav.connect():
        print("Connected!")
        
        # Get telemetry
        for i in range(10):
            tel = mav.get_telemetry()
            if tel:
                print(f"Position: {tel.get('lat', 0):.7f}, {tel.get('lon', 0):.7f}, Alt: {tel.get('alt', 0):.1f}m")
                print(f"Attitude: R={tel.get('roll', 0):.1f}°, P={tel.get('pitch', 0):.1f}°, Y={tel.get('yaw', 0):.1f}°")
                print(f"Battery: {tel.get('battery_voltage', 0):.2f}V")
            time.sleep(1)
            
        # Example commands
        print("\nSending test commands...")
        
        # Arm
        if mav.arm():
            print("Armed!")
            
        # Takeoff
        if mav.takeoff(10):
            print("Takeoff command sent")
            
        # Disarm
        time.sleep(2)
        mav.disarm()
        
        # Disconnect
        mav.disconnect()
    else:
        print("Connection failed!")
        print("Usage: python real_mavlink.py <connection_string>")
        print("Examples:")
        print("  serial:/dev/ttyUSB0:921600")
        print("  tcp:localhost:5760")
        print("  udp:localhost:14550")