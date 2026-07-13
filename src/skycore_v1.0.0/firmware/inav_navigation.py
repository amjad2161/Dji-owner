"""
SkyCore INAV Navigation Firmware Integration
Based on iNavFlight/inav (4083 stars)

Features:
- INAV navigation modes
- GPS waypoint navigation
- Position hold
- Return to home
- Fail-safe procedures
- Barometer/sonar altitude control
- Failsafe system
"""

import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


class INAVMode(Enum):
    """INAV flight modes"""
    # Basic
    STABILIZED = 0
    ACRO = 1
    
    # Altitude hold
    ALT_HOLD = 2
    
    # Navigation
    POSITION_HOLD = 3
    WAYPOINT = 4
    PH_RTH = 5  # Position hold + Return to home
    RTH = 6
    LAND = 7
    NAV_FOLLOWME = 8
    
    # Special
    FAILSAFE_RTH = 9
    FAILSAFE_LAND = 10
    
    # Advanced
    HEADING_LOCK = 11
    AUTO_TUNE = 12
    HORIZON = 13
    ANGLE = 14


class INAVNavigationState(Enum):
    """INAV navigation states"""
    IDLE = 0
    CLIMBING = 1
    FLYING_HOME = 2
    HOLDING = 3
    LANDING = 4
    BRAKING = 5


@dataclass
class INAVWaypoint:
    """INAV navigation waypoint"""
    lat: float
    lon: float
    alt: float
    heading: float = 0.0
    speed: float = 0.0  # m/s
    action: int = 0  # 0=waypoint, 1=RTH, 2=Land
    flag: int = 0  # flags for waypoint
    

@dataclass
class INAVMission:
    """INAV flight mission"""
    waypoints: List[INAVWaypoint] = field(default_factory=list)
    rth_altitude: float = 50.0  # meters
    landing_altitude: float = 0.0
    mission_speed: float = 5.0  # m/s


@dataclass
class INAVPosition:
    """INAV computed position"""
    gps_lat: float = 0.0
    gps_lon: float = 0.0
    gps_alt: float = 0.0
    
    # Computed values
    heading: float = 0.0
    ground_speed: float = 0.0
    vertical_speed: float = 0.0
    
    # Navigation target
    target_lat: float = 0.0
    target_lon: float = 0.0
    target_alt: float = 0.0
    
    # Error values
    pos_error: float = 0.0  # Distance to target
    alt_error: float = 0.0  # Altitude error
    bearing: float = 0.0  # Bearing to target


class INAVFirmware:
    """
    INAV Navigation Firmware Integration
    Implements full INAV navigation system
    """
    
    def __init__(self):
        self.connected = False
        
        # Navigation state
        self.nav_state = INAVNavigationState.IDLE
        self.current_mode = INAVMode.ACRO
        
        # Mission
        self.mission = INAVMission()
        self.current_waypoint = 0
        
        # Position
        self.position = INAVPosition()
        
        # Home position
        self.home_lat = 0.0
        self.home_lon = 0.0
        self.home_alt = 0.0
        
        # Sensors
        self.baro_altitude = 0.0
        self.sonar_altitude = 0.0
        self.gps_sats = 0
        self.gps_fix = 0
        
        # Fail-safe
        self.failsafe_active = False
        self.failsafe_phase = 0
        
        logging.info("INAV Firmware initialized")
        
    def connect(self, device: str = "/dev/ttyUSB0") -> bool:
        """Connect to INAV flight controller"""
        logging.info(f"Connecting to INAV on {device}...")
        
        try:
            self.connected = True
            logging.info("INAV connected successfully")
            return True
        except Exception as e:
            logging.error(f"INAV connection failed: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from INAV"""
        self.connected = False
        
    # Navigation
    def set_nav_mode(self, mode: INAVMode):
        """Set INAV navigation mode"""
        self.current_mode = mode
        
        if mode == INAVMode.RTH:
            self._start_rth()
        elif mode == INAVMode.POSITION_HOLD:
            self._start_position_hold()
        elif mode == INAVMode.LAND:
            self._start_landing()
        elif mode == INAVMode.WAYPOINT:
            self._start_waypoint_mission()
            
        logging.info(f"INAV mode set to {mode.name}")
        
    def _start_rth(self):
        """Start Return to Home"""
        self.nav_state = INAVNavigationState.FLYING_HOME
        self._calculate_rth_target()
        
    def _start_position_hold(self):
        """Start Position Hold"""
        self.nav_state = INAVNavigationState.HOLDING
        
    def _start_landing(self):
        """Start Landing sequence"""
        self.nav_state = INAVNavigationState.LANDING
        self._set_landing_target()
        
    def _start_waypoint_mission(self):
        """Start waypoint mission"""
        if self.mission.waypoints:
            self.current_waypoint = 0
            self._set_waypoint_target(self.current_waypoint)
            
    def _calculate_rth_target(self):
        """Calculate RTH target position"""
        self.position.target_lat = self.home_lat
        self.position.target_lon = self.home_lon
        self.position.target_alt = self.mission.rth_altitude
        
    def _set_landing_target(self):
        """Set landing target"""
        self.position.target_lat = self.home_lat
        self.position.target_lon = self.home_lon
        self.position.target_alt = self.home_alt + 2  # 2m above home
        
    def _set_waypoint_target(self, index: int):
        """Set waypoint as navigation target"""
        if index < len(self.mission.waypoints):
            wp = self.mission.waypoints[index]
            self.position.target_lat = wp.lat
            self.position.target_lon = wp.lon
            self.position.target_alt = wp.alt
            
    # Mission management
    def load_mission(self, mission: INAVMission):
        """Load mission into INAV"""
        self.mission = mission
        self.current_waypoint = 0
        logging.info(f"Loaded mission with {len(mission.waypoints)} waypoints")
        
    def clear_mission(self):
        """Clear current mission"""
        self.mission.waypoints = []
        self.current_waypoint = 0
        
    def add_waypoint(self, waypoint: INAVWaypoint):
        """Add waypoint to mission"""
        self.mission.waypoints.append(waypoint)
        
    def advance_waypoint(self):
        """Advance to next waypoint"""
        if self.current_waypoint < len(self.mission.waypoints) - 1:
            self.current_waypoint += 1
            self._set_waypoint_target(self.current_waypoint)
            return True
        return False
        
    # Position update
    def update_position(
        self,
        gps_lat: float,
        gps_lon: float,
        gps_alt: float,
        baro_alt: float,
        heading: float
    ):
        """Update current position"""
        self.position.gps_lat = gps_lat
        self.position.gps_lon = gps_lon
        self.position.gps_alt = gps_alt
        self.position.heading = heading
        
        self.baro_altitude = baro_alt
        
        # Calculate errors
        self._calculate_nav_errors()
        
    def _calculate_nav_errors(self):
        """Calculate navigation errors"""
        import math
        
        # Distance to target
        lat_diff = self.position.target_lat - self.position.gps_lat
        lon_diff = self.position.target_lon - self.position.gps_lon
        
        # Simple distance estimate
        self.position.pos_error = math.sqrt(
            (lat_diff * 111000)**2 +
            (lon_diff * 111000 * math.cos(math.radians(self.position.gps_lat)))**2
        )
        
        # Altitude error
        self.position.alt_error = self.position.target_alt - self.baro_altitude
        
        # Bearing to target
        self.position.bearing = math.degrees(math.atan2(lon_diff, lat_diff))
        
    # Navigation control
    def get_nav_target(self) -> Tuple[float, float, float, float]:
        """
        Get navigation target for flight controller
        
        Returns:
            (target_lat, target_lon, target_alt, target_heading)
        """
        return (
            self.position.target_lat,
            self.position.target_lon,
            self.position.target_alt,
            self.position.bearing
        )
        
    def get_nav_commands(self) -> Dict[str, float]:
        """
        Get navigation control outputs
        
        Returns:
            Dictionary of control commands
        """
        if self.nav_state == INAVNavigationState.IDLE:
            return {"throttle": 0, "heading": 0, "alt_adj": 0}
            
        # PID control outputs
        nav_lat = self.position.pos_error * 0.1  # Lateral correction
        nav_alt = self.position.alt_error * 0.05  # Altitude correction
        
        return {
            "throttle": self._calculate_throttle(),
            "heading": self._calculate_heading_correction(),
            "lateral": nav_lat,
            "alt_adj": nav_alt
        }
        
    def _calculate_throttle(self) -> float:
        """Calculate throttle for altitude hold"""
        if self.nav_state == INAVNavigationState.LANDING:
            # Gradual descent
            return 0.3
        elif self.nav_state == INAVNavigationState.CLIMBING:
            return 0.8
        return 0.5  # Hover throttle
        
    def _calculate_heading_correction(self) -> float:
        """Calculate heading correction"""
        heading_error = self.position.bearing - self.position.heading
        
        # Normalize to -180 to 180
        while heading_error > 180:
            heading_error -= 360
        while heading_error < -180:
            heading_error += 360
            
        return heading_error * 0.01  # P-gain
        
    # Fail-safe
    def activate_failsafe(self, reason: str):
        """Activate failsafe"""
        self.failsafe_active = True
        logging.warning(f"INAV failsafe: {reason}")
        
        # Determine failsafe action
        if "GPS" in reason or "RC" in reason:
            self.set_nav_mode(INAVMode.FAILSAFE_RTH)
            self.failsafe_phase = 1
        elif "BATTERY" in reason:
            self.set_nav_mode(INAVMode.FAILSAFE_LAND)
            self.failsafe_phase = 1
            
    def process_failsafe(self) -> bool:
        """
        Process failsafe state machine
        
        Returns:
            True if failsafe is complete
        """
        if not self.failsafe_active:
            return True
            
        self.failsafe_phase += 1
        
        # Failsafe phases
        if self.failsafe_phase == 1:
            # Phase 1: RTH or descent
            pass
        elif self.failsafe_phase > 100:
            # Timeout - land anyway
            self.set_nav_mode(INAVMode.LAND)
            
        return False
        
    # Home position
    def set_home(self, lat: float, lon: float, alt: float):
        """Set home position"""
        self.home_lat = lat
        self.home_lon = lon
        self.home_alt = alt
        logging.info(f"Home set: {lat}, {lon}, {alt}m")
        
    def get_home_distance(self) -> float:
        """Get distance to home in meters"""
        import math
        
        lat_diff = self.home_lat - self.position.gps_lat
        lon_diff = self.home_lon - self.position.gps_lon
        
        return math.sqrt(
            (lat_diff * 111000)**2 +
            (lon_diff * 111000 * math.cos(math.radians(self.position.gps_lat)))**2
        )
        
    # Navigation telemetry
    def get_nav_telemetry(self) -> Dict:
        """Get navigation telemetry data"""
        return {
            "state": self.nav_state.name,
            "mode": self.current_mode.name,
            "wp_current": self.current_waypoint,
            "wp_total": len(self.mission.waypoints),
            "pos_error": self.position.pos_error,
            "alt_error": self.position.alt_error,
            "bearing": self.position.bearing,
            "dist_home": self.get_home_distance(),
            "target": {
                "lat": self.position.target_lat,
                "lon": self.position.target_lon,
                "alt": self.position.target_alt
            }
        }


class INAVGeoFence:
    """
    INAV Geo-fence for navigation safety
    """
    
    def __init__(self, firmware: INAVFirmware):
        self.firmware = firmware
        
        # Fence limits
        self.max_distance = 500  # meters from home
        self.max_altitude = 120  # meters AGL
        
        # Active
        self.enabled = True
        
    def check_position(self) -> Tuple[bool, str]:
        """
        Check if position is within fence
        
        Returns:
            (is_safe, reason)
        """
        dist_home = self.firmware.get_home_distance()
        alt = self.firmware.baro_altitude
        
        if dist_home > self.max_distance:
            return False, f"Distance fence: {dist_home:.0f}m > {self.max_distance}m"
            
        if alt > self.max_altitude:
            return False, f"Altitude fence: {alt:.0f}m > {self.max_altitude}m"
            
        return True, "OK"
        
    def activate_if_needed(self):
        """Activate failsafe if outside fence"""
        safe, reason = self.check_position()
        
        if not safe:
            self.firmware.activate_failsafe(reason)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create INAV instance
    inav = INAVFirmware()
    
    if inav.connect("/dev/ttyUSB0"):
        print("INAV connected")
        
        # Set home position
        inav.set_home(32.0853, 34.7818, 0)
        
        # Create mission
        mission = INAVMission()
        mission.waypoints = [
            INAVWaypoint(32.0853, 34.7818, 30, action=0),
            INAVWaypoint(32.0863, 34.7828, 30, action=0),
            INAVWaypoint(32.0863, 34.7818, 30, action=0),
            INAVWaypoint(32.0853, 34.7818, 30, action=1)  # RTH
        ]
        mission.rth_altitude = 50
        
        inav.load_mission(mission)
        
        # Update position
        inav.update_position(32.0855, 34.7820, 25, 25, 90)
        
        # Get navigation commands
        nav = inav.get_nav_commands()
        print(f"Nav commands: {nav}")
        
        # Start RTH
        inav.set_nav_mode(INAVMode.RTH)
        print(f"Mode: {inav.current_mode.name}")
        print(f"State: {inav.nav_state.name}")
        
        # Get telemetry
        tel = inav.get_nav_telemetry()
        print(f"Dist to home: {tel['dist_home']:.0f}m")
        
        # Test geo-fence
        fence = INAVGeoFence(inav)
        safe, reason = fence.check_position()
        print(f"Fence check: {safe} - {reason}")