"""
SkyCore Missions - Litchi CSV Import/Export
===========================================
Litchi mission format support for waypoint missions.
"""

import csv
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class LitchiWaypoint:
    """Litchi waypoint format."""
    index: int
    latitude: float
    longitude: float
    altitude: float
    heading: float = 0.0  # degrees
    curvature: float = 0.0  # turn rate
    gimbal_pitch: float = -90.0  # degrees
    gimbal_yaw: float = 0.0  # degrees
    photo_trigger: bool = False
    hover_time: float = 0.0  # seconds
    speed: float = 0.0  # m/s (0 = default)
    
    def to_dict(self) -> Dict:
        return {
            'index': self.index,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude': self.altitude,
            'heading': self.heading,
            'curvature': self.curvature,
            'gimbal_pitch': self.gimbal_pitch,
            'gimbal_yaw': self.gimbal_yaw,
            'photo_trigger': int(self.photo_trigger),
            'hover_time': self.hover_time,
            'speed': self.speed
        }


class LitchiMission:
    """
    Litchi CSV mission format handler.
    
    Supports:
    - Import Litchi CSV missions
    - Export missions to Litchi CSV format
    - Convert between SkyCore mission format and Litchi
    """
    
    # Litchi CSV column names
    LITCHI_COLUMNS = [
        'idx', 'lat', 'lng', 'alt', 'heading', 'curvature',
        'poi_lat', 'poi_lng', 'poi_alt', 'gimbal_pitch', 'gimbal_yaw',
        'photo_time', 'photo_interval', 'photo_trigger', 'hover_time',
        'repeat', 'speed', 'motor_on', 'heading_mode', 'idle_speed',
        'utc_time', 'utc_offset', 'dv', 'dn', 'de', 'altitude_type'
    ]
    
    def __init__(self):
        self.waypoints: List[LitchiWaypoint] = []
        self.mission_name: str = ""
        self.home_lat: float = 0.0
        self.home_lon: float = 0.0
    
    @classmethod
    def from_csv(cls, csv_path: str) -> 'LitchiMission':
        """
        Import mission from Litchi CSV file.
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            LitchiMission with waypoints
        """
        mission = cls()
        
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    try:
                        wp = LitchiWaypoint(
                            index=int(row.get('idx', 0)),
                            latitude=float(row.get('lat', 0)),
                            longitude=float(row.get('lng', 0)),
                            altitude=float(row.get('alt', 50)),
                            heading=float(row.get('heading', 0)),
                            gimbal_pitch=float(row.get('gimbal_pitch', -90)),
                            gimbal_yaw=float(row.get('gimbal_yaw', 0)),
                            photo_trigger=bool(int(row.get('photo_trigger', 0))),
                            hover_time=float(row.get('hover_time', 0)),
                            speed=float(row.get('speed', 0))
                        )
                        mission.waypoints.append(wp)
                    except (ValueError, KeyError) as e:
                        log.warning(f"Failed to parse waypoint: {e}")
                        continue
        
            mission.mission_name = Path(csv_path).stem
            log.info(f"Imported {len(mission.waypoints)} waypoints from {csv_path}")
            
        except Exception as e:
            log.error(f"Failed to import Litchi CSV: {e}")
        
        return mission
    
    def to_csv(self, csv_path: str):
        """
        Export mission to Litchi CSV format.
        
        Args:
            csv_path: Output CSV file path
        """
        if not self.waypoints:
            log.warning("No waypoints to export")
            return
        
        try:
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.LITCHI_COLUMNS)
                writer.writeheader()
                
                for wp in self.waypoints:
                    row = {
                        'idx': wp.index,
                        'lat': wp.latitude,
                        'lng': wp.longitude,
                        'alt': wp.altitude,
                        'heading': wp.heading,
                        'curvature': 0,  # Litchi curvature
                        'poi_lat': wp.latitude,  # POI at waypoint
                        'poi_lng': wp.longitude,
                        'poi_alt': 0,  # POI altitude (auto)
                        'gimbal_pitch': wp.gimbal_pitch,
                        'gimbal_yaw': wp.gimbal_yaw,
                        'photo_time': 0,  # Photo time
                        'photo_interval': 0,  # Photo interval
                        'photo_trigger': int(wp.photo_trigger),
                        'hover_time': wp.hover_time,
                        'repeat': 1,
                        'speed': wp.speed,
                        'motor_on': 1,
                        'heading_mode': 0,  # Use waypoint heading
                        'idle_speed': 0,
                        'utc_time': '',
                        'utc_offset': '',
                        'dv': 0,
                        'dn': 0,
                        'de': 0,
                        'altitude_type': 0  # MSL altitude
                    }
                    writer.writerow(row)
            
            log.info(f"Exported {len(self.waypoints)} waypoints to {csv_path}")
            
        except Exception as e:
            log.error(f"Failed to export Litchi CSV: {e}")
    
    @classmethod
    def from_skycore_mission(cls, mission_data: Dict) -> 'LitchiMission':
        """
        Convert SkyCore mission to Litchi format.
        
        Args:
            mission_data: SkyCore mission dictionary with waypoints
            
        Returns:
            LitchiMission
        """
        mission = cls()
        mission.mission_name = mission_data.get('name', 'Imported Mission')
        
        waypoints = mission_data.get('waypoints', [])
        
        for i, wp in enumerate(waypoints):
            litchi_wp = LitchiWaypoint(
                index=i,
                latitude=wp.get('lat', 0),
                longitude=wp.get('lon', 0),
                altitude=wp.get('alt', 50),
                heading=wp.get('yaw', 0),
                gimbal_pitch=wp.get('gimbal_pitch', -90),
                photo_trigger=wp.get('photo_trigger', False),
                hover_time=wp.get('hover_time', 0),
                speed=wp.get('speed', 0)
            )
            mission.waypoints.append(litchi_wp)
        
        return mission
    
    def to_skycore_mission(self) -> Dict:
        """
        Convert Litchi mission to SkyCore format.
        
        Returns:
            SkyCore mission dictionary
        """
        waypoints = []
        
        for litchi_wp in self.waypoints:
            waypoints.append({
                'lat': litchi_wp.latitude,
                'lon': litchi_wp.longitude,
                'alt': litchi_wp.altitude,
                'yaw': litchi_wp.heading,
                'gimbal_pitch': litchi_wp.gimbal_pitch,
                'gimbal_yaw': litchi_wp.gimbal_yaw,
                'photo_trigger': litchi_wp.photo_trigger,
                'hover_time': litchi_wp.hover_time,
                'speed': litchi_wp.speed
            })
        
        return {
            'name': self.mission_name,
            'type': 'litchi_import',
            'waypoints': waypoints,
            'waypoint_count': len(waypoints)
        }
    
    def add_waypoint(self, lat: float, lon: float, alt: float, **kwargs):
        """Add waypoint to mission."""
        wp = LitchiWaypoint(
            index=len(self.waypoints),
            latitude=lat,
            longitude=lon,
            altitude=alt,
            **kwargs
        )
        self.waypoints.append(wp)
    
    def insert_waypoint(self, index: int, lat: float, lon: float, alt: float, **kwargs):
        """Insert waypoint at specific index."""
        wp = LitchiWaypoint(
            index=index,
            latitude=lat,
            longitude=lon,
            altitude=alt,
            **kwargs
        )
        self.waypoints.insert(index, wp)
        # Reindex
        for i, waypoint in enumerate(self.waypoints):
            waypoint.index = i
    
    def remove_waypoint(self, index: int):
        """Remove waypoint at index."""
        if 0 <= index < len(self.waypoints):
            self.waypoints.pop(index)
            # Reindex
            for i, waypoint in enumerate(self.waypoints):
                waypoint.index = i
    
    def clear(self):
        """Clear all waypoints."""
        self.waypoints.clear()
    
    def get_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """Get mission bounding box (min_lat, min_lon, max_lat, max_lon)."""
        if not self.waypoints:
            return None
        
        lats = [wp.latitude for wp in self.waypoints]
        lons = [wp.longitude for wp in self.waypoints]
        
        return (
            min(lats),
            min(lons),
            max(lats),
            max(lons)
        )
    
    def get_total_distance(self) -> float:
        """Calculate total mission distance in meters."""
        import math
        
        if len(self.waypoints) < 2:
            return 0.0
        
        total = 0.0
        
        for i in range(1, len(self.waypoints)):
            prev = self.waypoints[i - 1]
            curr = self.waypoints[i]
            
            # Haversine distance
            R = 6371000  # Earth radius in meters
            lat1, lon1 = math.radians(prev.latitude), math.radians(prev.longitude)
            lat2, lon2 = math.radians(curr.latitude), math.radians(curr.longitude)
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            
            distance = R * c
            
            # Add altitude difference
            alt_diff = abs(curr.altitude - prev.altitude)
            distance = math.sqrt(distance**2 + alt_diff**2)
            
            total += distance
        
        return total
    
    def get_estimated_duration(self, avg_speed: float = 10.0) -> float:
        """Estimate mission duration in seconds."""
        distance = self.get_total_distance()
        return distance / avg_speed
    
    def optimize_order(self, optimize: bool = True):
        """
        Optimize waypoint order using nearest-neighbor algorithm.
        
        Args:
            optimize: Whether to optimize (False keeps original order)
        """
        if not optimize or len(self.waypoints) <= 2:
            return
        
        import math
        
        # Simple nearest-neighbor optimization
        remaining = list(range(1, len(self.waypoints)))
        ordered = [0]  # Start from first waypoint
        
        while remaining:
            current = self.waypoints[ordered[-1]]
            nearest_idx = None
            nearest_dist = float('inf')
            
            for idx in remaining:
                wp = self.waypoints[idx]
                
                R = 6371000
                lat1, lon1 = math.radians(current.latitude), math.radians(current.longitude)
                lat2, lon2 = math.radians(wp.latitude), math.radians(wp.longitude)
                
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                
                dist = R * c
                
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest_idx = idx
            
            if nearest_idx is not None:
                ordered.append(nearest_idx)
                remaining.remove(nearest_idx)
        
        # Reorder waypoints
        new_waypoints = [self.waypoints[i] for i in ordered]
        self.waypoints = new_waypoints
        
        # Reindex
        for i, wp in enumerate(self.waypoints):
            wp.index = i
    
    def get_statistics(self) -> Dict:
        """Get mission statistics."""
        return {
            'name': self.mission_name,
            'waypoint_count': len(self.waypoints),
            'total_distance_m': round(self.get_total_distance(), 2),
            'estimated_duration_sec': round(self.get_estimated_duration(), 2),
            'bounds': self.get_bounds(),
            'avg_altitude': sum(wp.altitude for wp in self.waypoints) / max(1, len(self.waypoints)),
            'photo_count': sum(1 for wp in self.waypoints if wp.photo_trigger)
        }


def import_litchi_csv(path: str) -> Dict:
    """Import Litchi CSV and return SkyCore mission format."""
    mission = LitchiMission.from_csv(path)
    return mission.to_skycore_mission()


def export_litchi_csv(mission_data: Dict, path: str):
    """Export SkyCore mission to Litchi CSV format."""
    mission = LitchiMission.from_skycore_mission(mission_data)
    mission.to_csv(path)


# Export
__all__ = ['LitchiMission', 'LitchiWaypoint', 'import_litchi_csv', 'export_litchi_csv']