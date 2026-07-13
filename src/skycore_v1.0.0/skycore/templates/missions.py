"""
SkyCore Mission Templates
========================
Ready-made mission generators for common drone operations.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger(__name__)


class MissionTemplate(Enum):
    """Available mission templates."""
    PANORAMA = "panorama"
    PERIMETER_PATROL = "perimeter_patrol"
    BUILDING_INSPECTION = "building_inspection"
    HYPERLAPSE_LINE = "hyperlapse_line"
    VERTICAL_PANORAMA = "vertical_panorama"
    SPIRALING_ORBIT = "spiraling_orbit"
    FACADE_SCAN = "facade_scan"
    CINEMATIC_REVEAL = "cinematic_reveal"


@dataclass
class Waypoint:
    """Mission waypoint."""
    lat: float
    lon: float
    alt: float
    yaw: float = 0.0
    speed: float = 5.0  # m/s
    gimbal_pitch: float = -90.0  # degrees (nadir)
    photo_trigger: bool = False
    hover_time: float = 0.0  # seconds
    
    def to_dict(self) -> Dict:
        return {
            'lat': self.lat,
            'lon': self.lon,
            'alt': self.alt,
            'yaw': self.yaw,
            'speed': self.speed,
            'gimbal_pitch': self.gimbal_pitch,
            'photo_trigger': self.photo_trigger,
            'hover_time': self.hover_time
        }


@dataclass
class MissionSpec:
    """Mission specification."""
    name: str
    template: MissionTemplate
    waypoints: List[Waypoint]
    parameters: Dict = field(default_factory=dict)
    estimated_duration_sec: float = 0.0
    estimated_distance_m: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'template': self.template.value,
            'waypoints': [w.to_dict() for w in self.waypoints],
            'parameters': self.parameters,
            'estimated_duration_sec': self.estimated_duration_sec,
            'estimated_distance_m': self.estimated_distance_m
        }


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate haversine distance in meters."""
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate bearing from point 1 to point 2."""
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    
    y = math.sin(dlon) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
    
    bearing = math.atan2(y, x)
    return (math.degrees(bearing) + 360) % 360


class MissionTemplates:
    """
    Mission template library.
    
    Generates pre-configured missions for common operations:
    - Panoramas (multi-row, vertical, 360°)
    - Perimeter patrols
    - Building inspections
    - Hyperlapse lines
    - Facade scans
    - Cinematic reveals
    """
    
    @staticmethod
    def panorama_mission(center_lat: float, center_lon: float,
                        start_alt: float = 50.0,
                        radius: float = 30.0,
                        rows: int = 3,
                        photos_per_row: int = 8,
                        gimbal_pitch: float = -45.0) -> MissionSpec:
        """
        Generate multi-row panorama mission.
        
        Args:
            center_lat, center_lon: Center point
            start_alt: Starting altitude
            radius: Orbit radius
            rows: Number of altitude rows
            photos_per_row: Photos per row
            gimbal_pitch: Gimbal pitch angle
            
        Returns:
            MissionSpec with waypoints
        """
        waypoints = []
        alt_increment = 20.0
        
        for row in range(rows):
            alt = start_alt + row * alt_increment
            yaw_increment = 360 / photos_per_row
            
            for photo in range(photos_per_row):
                yaw = photo * yaw_increment
                angle_rad = math.radians(yaw)
                
                lat = center_lat + (radius / 111320) * math.cos(angle_rad)
                lon = center_lon + (radius / (111320 * math.cos(math.radians(center_lat)))) * math.sin(angle_rad)
                
                waypoints.append(Waypoint(
                    lat=lat, lon=lon, alt=alt,
                    yaw=yaw, speed=3.0,
                    gimbal_pitch=gimbal_pitch,
                    photo_trigger=True,
                    hover_time=2.0
                ))
        
        name = f"Panorama Row {rows}x{photos_per_row}"
        
        return MissionSpec(
            name=name,
            template=MissionTemplate.PANORAMA,
            waypoints=waypoints,
            parameters={
                'center': (center_lat, center_lon),
                'radius': radius,
                'rows': rows,
                'photos_per_row': photos_per_row
            }
        )
    
    @staticmethod
    def perimeter_patrol(points: List[Tuple[float, float]],
                       altitude: float = 50.0,
                       corner_heading: bool = True,
                       photo_trigger: bool = True) -> MissionSpec:
        """
        Generate perimeter patrol mission.
        
        Args:
            points: List of (lat, lon) polygon vertices
            altitude: Flight altitude
            corner_heading: True to face corners at waypoints
            photo_trigger: Trigger photo at each waypoint
            
        Returns:
            MissionSpec with waypoints
        """
        if len(points) < 3:
            raise ValueError("Need at least 3 points for perimeter")
        
        waypoints = []
        
        for i, (lat, lon) in enumerate(points):
            # Calculate heading to next point
            if corner_heading:
                next_idx = (i + 1) % len(points)
                next_lat, next_lon = points[next_idx]
                yaw = _bearing(lat, lon, next_lat, next_lon)
            else:
                yaw = 0.0
            
            waypoints.append(Waypoint(
                lat=lat, lon=lon, alt=altitude,
                yaw=yaw, speed=5.0,
                photo_trigger=photo_trigger
            ))
        
        return MissionSpec(
            name="Perimeter Patrol",
            template=MissionTemplate.PERIMETER_PATROL,
            waypoints=waypoints,
            parameters={'points': points, 'altitude': altitude}
        )
    
    @staticmethod
    def building_inspection(building_lat: float, building_lon: float,
                           building_height: float = 30.0,
                           orbit_radius: float = 20.0,
                           orbit_altitudes: List[float] = None) -> MissionSpec:
        """
        Generate building inspection mission with stacked orbits.
        
        Args:
            building_lat, building_lon: Building center
            building_height: Building height for orbit altitudes
            orbit_radius: Radius from building
            orbit_altitudes: List of altitudes for orbits
            
        Returns:
            MissionSpec with waypoints
        """
        if orbit_altitudes is None:
            orbit_altitudes = [building_height + 10, building_height + 25, building_height + 40]
        
        waypoints = []
        photos_per_orbit = 8
        
        for alt in orbit_altitudes:
            yaw_increment = 360 / photos_per_orbit
            
            for photo in range(photos_per_orbit):
                yaw = photo * yaw_increment
                angle_rad = math.radians(yaw)
                
                lat = building_lat + (orbit_radius / 111320) * math.cos(angle_rad)
                lon = building_lon + (orbit_radius / (111320 * math.cos(math.radians(building_lat)))) * math.sin(angle_rad)
                
                # Point gimbal at building
                gimbal_pitch = -math.degrees(math.atan2(orbit_radius, alt - building_height)) if alt > building_height else -60
                
                waypoints.append(Waypoint(
                    lat=lat, lon=lon, alt=alt,
                    yaw=yaw, speed=3.0,
                    gimbal_pitch=gimbal_pitch,
                    photo_trigger=True,
                    hover_time=3.0
                ))
        
        return MissionSpec(
            name=f"Building Inspection ({len(orbit_altitudes)} orbits)",
            template=MissionTemplate.BUILDING_INSPECTION,
            waypoints=waypoints,
            parameters={
                'building': (building_lat, building_lon),
                'height': building_height,
                'radius': orbit_radius
            }
        )
    
    @staticmethod
    def hyperlapse_line(start_lat: float, start_lon: float,
                       end_lat: float, end_lon: float,
                       num_points: int = 20,
                       altitude: float = 50.0,
                       gimbal_pitch: float = -90.0) -> MissionSpec:
        """
        Generate hyperlapse mission along a line.
        
        Args:
            start_lat, start_lon: Start point
            end_lat, end_lon: End point
            num_points: Number of photo waypoints
            altitude: Flight altitude
            gimbal_pitch: Gimbal pitch (nadir for hyperlapse)
            
        Returns:
            MissionSpec with waypoints
        """
        waypoints = []
        
        for i in range(num_points):
            t = i / (num_points - 1)
            
            lat = start_lat + (end_lat - start_lat) * t
            lon = start_lon + (end_lon - start_lon) * t
            
            # Calculate yaw along path
            if i < num_points - 1:
                next_t = (i + 1) / (num_points - 1)
                next_lat = start_lat + (end_lat - start_lat) * next_t
                next_lon = start_lon + (end_lon - start_lon) * next_t
                yaw = _bearing(lat, lon, next_lat, next_lon)
            else:
                yaw = _bearing(start_lat, start_lon, end_lat, end_lon)
            
            waypoints.append(Waypoint(
                lat=lat, lon=lon, alt=altitude,
                yaw=yaw, speed=5.0,
                gimbal_pitch=gimbal_pitch,
                photo_trigger=True,
                hover_time=0.5
            ))
        
        distance = _haversine_distance(start_lat, start_lon, end_lat, end_lon)
        
        return MissionSpec(
            name=f"Hyperlapse Line ({num_points} points)",
            template=MissionTemplate.HYPERLAPSE_LINE,
            waypoints=waypoints,
            parameters={
                'start': (start_lat, start_lon),
                'end': (end_lat, end_lon),
                'distance_m': distance
            },
            estimated_distance_m=distance
        )
    
    @staticmethod
    def spiraling_orbit(center_lat: float, center_lon: float,
                       start_alt: float = 20.0,
                       end_alt: float = 80.0,
                       start_radius: float = 10.0,
                       end_radius: float = 40.0,
                       orbits: float = 3.0,
                       photos_per_orbit: int = 12) -> MissionSpec:
        """
        Generate spiraling orbit mission.
        
        Args:
            center_lat, center_lon: Orbit center
            start_alt, end_alt: Start and end altitudes
            start_radius, end_radius: Start and end radii
            orbits: Number of complete orbits
            photos_per_orbit: Photos per orbit
            
        Returns:
            MissionSpec with waypoints
        """
        waypoints = []
        total_photos = int(orbits * photos_per_orbit)
        
        for i in range(total_photos):
            t = i / (total_photos - 1)
            
            # Interpolate radius and altitude
            radius = start_radius + (end_radius - start_radius) * t
            alt = start_alt + (end_alt - start_alt) * t
            
            # Calculate angle
            angle = (i / photos_per_orbit) * 2 * math.pi
            yaw = math.degrees(angle)
            
            lat = center_lat + (radius / 111320) * math.cos(angle)
            lon = center_lon + (radius / (111320 * math.cos(math.radians(center_lat)))) * math.sin(angle)
            
            waypoints.append(Waypoint(
                lat=lat, lon=lon, alt=alt,
                yaw=yaw, speed=4.0,
                gimbal_pitch=-45.0,
                photo_trigger=True,
                hover_time=2.0
            ))
        
        return MissionSpec(
            name=f"Spiraling Orbit ({orbits} orbits)",
            template=MissionTemplate.SPIRALING_ORBIT,
            waypoints=waypoints,
            parameters={
                'center': (center_lat, center_lon),
                'start_alt': start_alt,
                'end_alt': end_alt,
                'start_radius': start_radius,
                'end_radius': end_radius,
                'orbits': orbits
            }
        )
    
    @staticmethod
    def facade_scan(building_lat: float, building_lon: float,
                   building_length: float = 50.0,
                   building_height: float = 30.0,
                   altitude: float = None,
                   passes: int = 3,
                   gimbal_pitch: float = -60.0) -> MissionSpec:
        """
        Generate facade scan (lawnmower pattern along building).
        
        Args:
            building_lat, building_lon: Building center
            building_length: Length of building
            building_height: Height for altitude calculation
            altitude: Override altitude
            passes: Number of lawnmower passes
            gimbal_pitch: Gimbal pitch for facade
            
        Returns:
            MissionSpec with waypoints
        """
        if altitude is None:
            altitude = building_height + 20
        
        waypoints = []
        
        # Calculate building boundaries
        path_length = building_length * 1.5
        side_offset = building_length * 0.3
        
        for pass_num in range(passes):
            # Alternate direction
            direction = 1 if pass_num % 2 == 0 else -1
            
            # Create two waypoints for this pass
            alt_offset = 10 * pass_num
            
            lat1 = building_lat - side_offset / 111320
            lon1 = building_lon + direction * path_length / (111320 * math.cos(math.radians(building_lat)))
            
            lat2 = building_lat + side_offset / 111320
            lon2 = building_lon - direction * path_length / (111320 * math.cos(math.radians(building_lat)))
            
            waypoints.append(Waypoint(
                lat=lat1, lon=lon1, alt=altitude + alt_offset,
                yaw=0 if direction > 0 else 180,
                speed=4.0,
                gimbal_pitch=gimbal_pitch,
                photo_trigger=True
            ))
            
            waypoints.append(Waypoint(
                lat=lat2, lon=lon2, alt=altitude + alt_offset,
                yaw=180 if direction > 0 else 0,
                speed=4.0,
                gimbal_pitch=gimbal_pitch,
                photo_trigger=True
            ))
        
        return MissionSpec(
            name=f"Facade Scan ({passes} passes)",
            template=MissionTemplate.FACADE_SCAN,
            waypoints=waypoints,
            parameters={
                'building': (building_lat, building_lon),
                'length': building_length,
                'height': building_height,
                'passes': passes
            }
        )


# Export
__all__ = ['MissionTemplates', 'MissionTemplate', 'MissionSpec', 'Waypoint']