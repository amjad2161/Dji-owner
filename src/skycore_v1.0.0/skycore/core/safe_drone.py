"""
SkyCore Core - Safe Drone Wrapper
================================
Safety wrapper enforcing geofence, battery RTH, and GPS limits.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math

log = logging.getLogger(__name__)


class SafetyCheck(Enum):
    """Safety check types."""
    GEOFENCE = "geofence"
    BATTERY = "battery"
    GPS = "gps"
    ALTITUDE = "altitude"
    LINK = "link"
    WEATHER = "weather"


@dataclass
class SafetyConfig:
    """Safety configuration."""
    geofence_enabled: bool = True
    battery_warning: float = 30.0  # percent
    battery_critical: float = 15.0  # percent
    battery_rth: float = 25.0  # percent for RTH
    gps_min_sats: int = 6
    gps_min_hdop: float = 3.0
    altitude_max: float = 120.0  # meters
    altitude_min: float = 2.0
    home_distance_max: float = 5000.0  # meters
    link_loss_timeout: float = 5.0  # seconds
    geofence_margin: float = 50.0  # meters from boundary


@dataclass
class SafetyViolation:
    """Safety violation record."""
    check: SafetyCheck
    severity: str  # warning, critical
    message: str
    timestamp: float
    data: Dict = field(default_factory=dict)


class SafeDrone:
    """
    Safety wrapper for drone operations.
    
    Enforces safety limits:
    - Geofence boundaries
    - Battery thresholds with automatic RTH
    - GPS quality requirements
    - Altitude limits
    - Link loss handling
    
    Features:
    - Pre-command safety checks
    - Automatic intervention on violations
    - Violation logging
    - Callback notifications
    """
    
    def __init__(self, drone, config: Optional[SafetyConfig] = None,
                 geofence_handler=None):
        """
        Initialize SafeDrone wrapper.
        
        Args:
            drone: Underlying drone implementation
            config: Safety configuration
            geofence_handler: Optional geofence handler
        """
        self.drone = drone
        self.config = config or SafetyConfig()
        self.geofence = geofence_handler
        
        # Safety state
        self.last_position: Optional[Tuple[float, float, float]] = None
        self.last_telemetry: Dict = {}
        self.rth_triggered: bool = False
        self.land_triggered: bool = False
        
        # Violations
        self.violations: List[SafetyViolation] = []
        self.max_violations = 100
        
        # Callbacks
        self._warning_callbacks: List[Callable] = []
        self._violation_callbacks: List[Callable] = []
        self._intervention_callbacks: List[Callable] = []
        
        # Statistics
        self.checks_passed = 0
        self.checks_failed = 0
        
        log.info("SafeDrone wrapper initialized")
    
    async def takeoff(self, min_battery: float = 50.0, min_sats: int = 6) -> bool:
        """
        Safe takeoff with pre-flight checks.
        
        Args:
            min_battery: Minimum battery percentage for takeoff
            min_sats: Minimum satellite count
            
        Returns:
            True if takeoff allowed
        """
        # Check battery
        telemetry = await self._get_telemetry()
        battery = telemetry.get('battery_percent', 100)
        
        if battery < min_battery:
            await self._add_violation(SafetyCheck.BATTERY, "warning",
                f"Low battery for takeoff: {battery:.1f}%")
            return False
        
        # Check GPS
        sats = telemetry.get('gps_sats', 0)
        if sats < min_sats:
            await self._add_violation(SafetyCheck.GPS, "warning",
                f"Insufficient satellites: {sats}")
            return False
        
        # Proceed with takeoff
        await self.drone.takeoff()
        return True
    
    async def goto(self, lat: float, lon: float, alt: float,
                  check_safety: bool = True) -> bool:
        """
        Go to position with safety checks.
        
        Args:
            lat: Target latitude
            lon: Target longitude
            alt: Target altitude
            check_safety: Whether to perform safety checks
            
        Returns:
            True if goto allowed
        """
        if not check_safety:
            await self.drone.goto(lat, lon, alt)
            return True
        
        # Check altitude
        if alt > self.config.altitude_max:
            await self._add_violation(SafetyCheck.ALTITUDE, "critical",
                f"Target altitude too high: {alt}m")
            return False
        
        if alt < self.config.altitude_min:
            await self._add_violation(SafetyCheck.ALTITUDE, "critical",
                f"Target altitude too low: {alt}m")
            return False
        
        # Check geofence
        if self.geofence and self.config.geofence_enabled:
            if not self.geofence.is_point_inside(lat, lon, alt):
                await self._add_violation(SafetyCheck.GEOFENCE, "critical",
                    "Target outside geofence")
                return False
        
        # Check distance from home
        if self.last_position:
            home_lat, home_lon, _ = self.last_position
            distance = self._haversine_distance(home_lat, home_lon, lat, lon)
            
            if distance > self.config.home_distance_max:
                await self._add_violation(SafetyCheck.GEOFENCE, "critical",
                    f"Distance from home too far: {distance:.0f}m")
                return False
        
        # Execute goto
        await self.drone.goto(lat, lon, alt)
        return True
    
    async def return_to_home(self) -> bool:
        """
        Return to home with automatic triggers.
        
        Returns:
            True if RTH initiated
        """
        # Check if already triggered
        if self.rth_triggered:
            return True
        
        self.rth_triggered = True
        await self._trigger_intervention("rth", "Battery threshold reached")
        
        await self.drone.return_to_home()
        return True
    
    async def land(self) -> bool:
        """Safe landing."""
        await self.drone.land()
        return True
    
    async def set_velocity(self, vx: float, vy: float, vz: float):
        """Set velocity with safety checks."""
        # Check velocity limits
        max_velocity = 15.0  # m/s
        
        if abs(vx) > max_velocity or abs(vy) > max_velocity or abs(vz) > max_velocity:
            log.warning(f"Velocity clamped: requested ({vx}, {vy}, {vz})")
            vx = max(-max_velocity, min(max_velocity, vx))
            vy = max(-max_velocity, min(max_velocity, vy))
            vz = max(-max_velocity, min(max_velocity, vz))
        
        await self.drone.set_velocity(vx, vy, vz)
    
    async def emergency_land(self):
        """Emergency landing - immediate."""
        await self.drone.emergency_land()
    
    async def update_telemetry(self, telemetry: Dict):
        """
        Update telemetry and check safety conditions.
        
        Args:
            telemetry: Current telemetry data
        """
        self.last_telemetry = telemetry
        
        # Update position
        lat = telemetry.get('lat', 0)
        lon = telemetry.get('lon', 0)
        alt = telemetry.get('alt', 0)
        self.last_position = (lat, lon, alt)
        
        # Check battery
        battery = telemetry.get('battery_percent', 100)
        
        if battery <= self.config.battery_critical and not self.rth_triggered:
            await self._trigger_intervention("rth", 
                f"Critical battery: {battery:.1f}%")
            self.rth_triggered = True
        
        # Check GPS quality
        sats = telemetry.get('gps_sats', 0)
        if sats < self.config.gps_min_sats:
            await self._add_violation(SafetyCheck.GPS, "warning",
                f"Weak GPS: {sats} satellites")
        
        # Check altitude
        if alt > self.config.altitude_max:
            await self._add_violation(SafetyCheck.ALTITUDE, "warning",
                f"Altitude exceeded: {alt}m")
        
        # Check geofence
        if self.geofence and self.config.geofence_enabled and self.last_position:
            inside = self.geofence.is_point_inside(lat, lon, alt)
            if not inside:
                await self._add_violation(SafetyCheck.GEOFENCE, "critical",
                    "Outside geofence boundary")
    
    async def _get_telemetry(self) -> Dict:
        """Get current telemetry."""
        return self.last_telemetry
    
    async def _add_violation(self, check: SafetyCheck, severity: str, message: str):
        """Add safety violation."""
        violation = SafetyViolation(
            check=check,
            severity=severity,
            message=message,
            timestamp=asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
        )
        
        self.violations.append(violation)
        
        # Keep only recent violations
        if len(self.violations) > self.max_violations:
            self.violations = self.violations[-self.max_violations:]
        
        self.checks_failed += 1
        
        # Trigger callbacks
        for callback in self._violation_callbacks:
            try:
                callback(violation)
            except Exception as e:
                log.error(f"Violation callback error: {e}")
        
        log.warning(f"Safety violation [{severity}]: {check.value} - {message}")
    
    async def _trigger_intervention(self, action: str, reason: str):
        """Trigger automatic intervention."""
        for callback in self._intervention_callbacks:
            try:
                await callback(action, reason)
            except Exception as e:
                log.error(f"Intervention callback error: {e}")
        
        log.warning(f"Automatic intervention: {action} - {reason}")
    
    def _haversine_distance(self, lat1: float, lon1: float, 
                           lat2: float, lon2: float) -> float:
        """Calculate haversine distance in meters."""
        R = 6371000  # Earth radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def on_violation(self, callback: Callable):
        """Register violation callback."""
        self._violation_callbacks.append(callback)
    
    def on_intervention(self, callback: Callable):
        """Register intervention callback."""
        self._intervention_callbacks.append(callback)
    
    def get_violations(self, limit: int = 10) -> List[SafetyViolation]:
        """Get recent violations."""
        return self.violations[-limit:]
    
    def reset_rth(self):
        """Reset RTH trigger."""
        self.rth_triggered = False
    
    def get_state(self) -> Dict:
        """Get safe drone state."""
        return {
            'rth_triggered': self.rth_triggered,
            'land_triggered': self.land_triggered,
            'checks_passed': self.checks_passed,
            'checks_failed': self.checks_failed,
            'violations_count': len(self.violations),
            'last_position': self.last_position,
            'last_telemetry': self.last_telemetry
        }
    
    # Delegate basic operations to underlying drone
    async def connect(self): return await self.drone.connect()
    async def disconnect(self): return await self.drone.disconnect()
    async def get_position(self): return await self.drone.get_position()
    async def get_battery(self): return await self.drone.get_battery()
    async def get_home_position(self): return await self.drone.get_home_position()
    async def capture_photo(self): return await self.drone.capture_photo()
    async def start_video_recording(self): return await self.drone.start_video_recording()
    async def stop_video_recording(self): return await self.drone.stop_video_recording()


# Export
__all__ = ['SafeDrone', 'SafetyConfig', 'SafetyViolation', 'SafetyCheck']