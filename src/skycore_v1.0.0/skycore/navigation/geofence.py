"""
SkyCore Geofence Validator
==========================
Geofence monitoring and violation detection.
"""

import numpy as np
from typing import Tuple, Dict, List, Optional
from dataclasses import dataclass
import math
import logging

log = logging.getLogger(__name__)


@dataclass
class GeofenceConfig:
    """Geofence configuration."""
    max_altitude: float = 120.0       # meters
    max_distance: float = 500.0       # meters from home
    min_distance: float = 5.0         # minimum altitude AGL
    home: Tuple[float, float, float] = (0, 0, 0)  # lat, lon, alt


@dataclass
class GeofenceZone:
    """Circular geofence zone."""
    center_lat: float
    center_lon: float
    center_alt: float
    radius_m: float
    max_alt_m: float = 999.0
    name: str = ""


class GeofenceValidator:
    """
    Geofence validator for drone operations.
    
    Monitors:
    - Maximum altitude
    - Maximum distance from home
    - Circular no-fly zones
    - Custom geofences
    """
    
    def __init__(self, config: Optional[GeofenceConfig] = None):
        """
        Initialize geofence validator.
        
        Args:
            config: Geofence configuration
        """
        self.config = config or GeofenceConfig()
        
        self.home_lat = self.config.home[0]
        self.home_lon = self.config.home[1]
        self.home_alt = self.config.home[2]
        
        # Custom zones
        self.zones: List[GeofenceZone] = []
        
        # Violation history
        self.violations: List[Dict] = []
        
        # Statistics
        self.total_checks = 0
        self.violation_count = 0
    
    def set_home(self, lat: float, lon: float, alt: float = 0.0):
        """Set home position."""
        self.home_lat = lat
        self.home_lon = lon
        self.home_alt = alt
    
    def add_zone(self, zone: GeofenceZone):
        """Add custom geofence zone."""
        self.zones.append(zone)
    
    def add_circular_zone(self, lat: float, lon: float, alt: float,
                         radius_m: float, max_alt_m: float = 999.0, name: str = ""):
        """Add circular no-fly zone."""
        self.zones.append(GeofenceZone(lat, lon, alt, radius_m, max_alt_m, name))
    
    def clear_zones(self):
        """Clear all custom zones."""
        self.zones.clear()
    
    def validate(self, lat: float, lon: float, alt: float) -> Dict:
        """
        Validate position against geofences.
        
        Args:
            lat: Latitude
            lon: Longitude
            alt: Altitude (meters)
            
        Returns:
            Validation result dictionary
        """
        self.total_checks += 1
        
        result = {
            'valid': True,
            'violations': [],
            'warnings': [],
            'distance_from_home': 0.0,
            'altitude_ok': True,
            'distance_ok': True,
            'zones_ok': True
        }
        
        # Check maximum altitude
        if alt > self.config.max_altitude:
            result['valid'] = False
            result['altitude_ok'] = False
            result['violations'].append({
                'type': 'MAX_ALTITUDE',
                'message': f'Altitude {alt:.1f}m exceeds maximum {self.config.max_altitude}m',
                'severity': 'critical'
            })
        
        # Check minimum altitude
        if alt < self.config.min_distance:
            result['warnings'].append({
                'type': 'MIN_ALTITUDE',
                'message': f'Altitude {alt:.1f}m below minimum {self.config.min_distance}m',
                'severity': 'warning'
            })
        
        # Check distance from home
        distance = self._haversine_distance(self.home_lat, self.home_lon, lat, lon)
        result['distance_from_home'] = distance
        
        if distance > self.config.max_distance:
            result['valid'] = False
            result['distance_ok'] = False
            result['violations'].append({
                'type': 'MAX_DISTANCE',
                'message': f'Distance {distance:.1f}m exceeds maximum {self.config.max_distance}m',
                'severity': 'critical'
            })
        
        # Check custom zones
        for zone in self.zones:
            zone_violation = self._check_zone(zone, lat, lon, alt)
            if zone_violation:
                if zone_violation['severity'] == 'critical':
                    result['valid'] = False
                    result['zones_ok'] = False
                result['violations'].append(zone_violation)
        
        # Record violation
        if not result['valid']:
            self.violation_count += 1
            self.violations.append({
                'timestamp': self.total_checks,
                'position': (lat, lon, alt),
                'violations': result['violations']
            })
        
        return result
    
    def _check_zone(self, zone: GeofenceZone, lat: float, lon: float, alt: float) -> Optional[Dict]:
        """Check if position violates a zone."""
        # Horizontal distance check
        dist = self._haversine_distance(zone.center_lat, zone.center_lon, lat, lon)
        
        if dist > zone.radius_m:
            return None  # Outside zone
        
        # Check altitude
        if alt > zone.max_alt_m:
            return {
                'type': 'ZONE_VIOLATION',
                'zone': zone.name,
                'message': f'In zone "{zone.name}" at {alt:.1f}m (max {zone.max_alt_m}m)',
                'severity': 'critical'
            }
        
        return {
            'type': 'ZONE_VIOLATION',
            'zone': zone.name,
            'message': f'Inside zone "{zone.name}"',
            'severity': 'warning'
        }
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great-circle distance in meters."""
        R = 6371000  # Earth radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        
        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def is_safe_to_fly(self, lat: float, lon: float, alt: float) -> Tuple[bool, str]:
        """
        Check if position is safe to fly.
        
        Returns:
            (is_safe, reason)
        """
        result = self.validate(lat, lon, alt)
        
        if result['valid']:
            return True, "All geofence checks passed"
        else:
            return False, result['violations'][0]['message']
    
    def get_distance_to_home(self, lat: float, lon: float) -> float:
        """Get distance from home in meters."""
        return self._haversine_distance(self.home_lat, self.home_lon, lat, lon)
    
    def get_distance_to_zone(self, zone: GeofenceZone, lat: float, lon: float) -> float:
        """Get distance to zone center."""
        return self._haversine_distance(zone.center_lat, zone.center_lon, lat, lon)
    
    def get_violation_history(self) -> List[Dict]:
        """Get violation history."""
        return self.violations
    
    def get_statistics(self) -> Dict:
        """Get geofence statistics."""
        return {
            'total_checks': self.total_checks,
            'violation_count': self.violation_count,
            'violation_rate': self.violation_count / max(1, self.total_checks),
            'active_zones': len(self.zones),
            'home_position': (self.home_lat, self.home_lon, self.home_alt)
        }
    
    def reset(self):
        """Reset validator."""
        self.violations.clear()
        self.total_checks = 0
        self.violation_count = 0