"""
SkyCore Airspace - OpenAIP Airspace Integration
Airspace classification and restriction awareness
"""

import json
import urllib.request
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class AirspaceZone:
    """Airspace zone definition"""
    id: str
    name: str
    classification: str  # 'A', 'B', 'C', 'D', 'E', 'F', 'G'
    floor_m_amsl: float
    ceiling_m_amsl: float
    geometry_type: str  # 'polygon', 'circle'
    geometry: List[Tuple[float, float]]  # List of (lat, lon) points
    restrictions: List[str]
    active_hours: str
    source: str


class OpenAIPClient:
    """OpenAIP airspace data client"""
    
    BASE_URL = "https://openaip.net/api/v2"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 3600  # 1 hour
        
    def _fetch(self, endpoint: str) -> Optional[Dict]:
        """Fetch data from OpenAIP API"""
        if endpoint in self.cache:
            if datetime.now().timestamp() - self.cache_time.get(endpoint, 0) < self.cache_duration:
                return self.cache[endpoint]
        
        try:
            url = f"{self.BASE_URL}{endpoint}"
            headers = {}
            if self.api_key:
                headers['X-API-Key'] = self.api_key
            
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode())
                
            self.cache[endpoint] = data
            self.cache_time[endpoint] = datetime.now().timestamp()
            return data
            
        except Exception as e:
            logger.warning(f"OpenAIP fetch failed: {e}")
            return None
    
    def get_airspace_by_region(self, region: str) -> List[AirspaceZone]:
        """Get airspace data for a region"""
        data = self._fetch(f"/airspaces/{region}")
        
        if not data:
            return []
        
        zones = []
        for item in data.get('airspaces', []):
            zone = AirspaceZone(
                id=item.get('id', ''),
                name=item.get('name', 'Unknown'),
                classification=item.get('class', 'G'),
                floor_m_amsl=item.get('bottom', {}).get('alt', 0),
                ceiling_m_amsl=item.get('top', {}).get('alt', 99999),
                geometry_type='polygon',
                geometry=item.get('geometry', []),
                restrictions=item.get('restrictions', []),
                active_hours=item.get('hours', 'H24'),
                source='openaip'
            )
            zones.append(zone)
        
        return zones


class AirspaceDatabase:
    """Local airspace database with common restrictions"""
    
    def __init__(self):
        # Common restricted areas for demo
        self.restricted_areas = [
            # Tel Aviv area
            {
                'name': 'Ben Gurion Airport CTR',
                'lat': 32.0055,
                'lon': 34.8854,
                'radius_m': 5000,
                'floor_m': 0,
                'ceiling_m': 1000,
                'class': 'D',
                'restrictions': ['No drones without permission', 'Contact tower 03-9772222']
            },
            # Haifa
            {
                'name': 'Haifa Airport CTR',
                'lat': 32.8111,
                'lon': 35.0431,
                'radius_m': 4000,
                'floor_m': 0,
                'ceiling_m': 800,
                'class': 'D',
                'restrictions': ['Controlled airspace', 'Prior permission required']
            },
            # Military bases (example)
            {
                'name': 'Military Base Zone',
                'lat': 31.8500,
                'lon': 34.6500,
                'radius_m': 3000,
                'floor_m': 0,
                'ceiling_m': 99999,
                'class': 'Prohibited',
                'restrictions': ['Prohibited area', 'No flight allowed']
            }
        ]
        
        # Pre-loaded airspace data
        self.zones = self._load_default_zones()
        
        logger.info(f"Airspace database initialized with {len(self.zones)} zones")
    
    def _load_default_zones(self) -> List[AirspaceZone]:
        """Load default airspace zones"""
        zones = []
        
        # Add restricted areas
        for area in self.restricted_areas:
            # Create circular geometry
            geometry = self._create_circle(
                area['lat'], area['lon'], area['radius_m']
            )
            
            zone = AirspaceZone(
                id=f"restricted_{len(zones)}",
                name=area['name'],
                classification=area['class'],
                floor_m_amsl=area['floor_m'],
                ceiling_m_amsl=area['ceiling_m'],
                geometry_type='circle',
                geometry=geometry,
                restrictions=area['restrictions'],
                active_hours='H24',
                source='local'
            )
            zones.append(zone)
        
        return zones
    
    def _create_circle(self, lat: float, lon: float, radius_m: float, num_points: int = 32) -> List[Tuple[float, float]]:
        """Create circular polygon geometry"""
        points = []
        import math
        
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            
            # Approximate: 1 degree lat = 111km, 1 degree lon = 111km * cos(lat)
            dlat = (radius_m / 111000) * math.cos(angle)
            dlon = (radius_m / (111000 * math.cos(math.radians(lat)))) * math.sin(angle)
            
            points.append((lat + dlat, lon + dlon))
        
        return points
    
    def query_point(self, lat: float, lon: float, altitude_m: float) -> List[AirspaceZone]:
        """Query airspace at a specific point"""
        matching = []
        
        for zone in self.zones:
            if self._point_in_zone(lat, lon, zone):
                if zone.floor_m_amsl <= altitude_m <= zone.ceiling_m_amsl:
                    matching.append(zone)
        
        return matching
    
    def _point_in_zone(self, lat: float, lon: float, zone: AirspaceZone) -> bool:
        """Check if point is inside zone"""
        import math
        
        if zone.geometry_type == 'circle' and len(zone.geometry) > 0:
            # First point is center for circle
            center = zone.geometry[0]
            center_lat, center_lon = center
            
            # Calculate distance
            dlat = (lat - center_lat) * 111000
            dlon = (lon - center_lon) * 111000 * math.cos(math.radians(lat))
            distance = math.sqrt(dlat**2 + dlon**2)
            
            # Check radius (approximate from geometry)
            if len(zone.geometry) >= 2:
                edge = zone.geometry[1]
                edge_lat, edge_lon = edge
                edlat = (edge_lat - center_lat) * 111000
                edlon = (edge_lon - center_lon) * 111000 * math.cos(math.radians(center_lat))
                radius = math.sqrt(edlat**2 + edlon**2)
                
                return distance <= radius
            
        elif zone.geometry_type == 'polygon':
            # Ray casting algorithm
            inside = False
            n = len(zone.geometry)
            
            for i in range(n):
                j = (i + 1) % n
                yi, xi = zone.geometry[i]
                yj, xj = zone.geometry[j]
                
                if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
                    inside = not inside
            
            return inside
        
        return False
    
    def is_critical_at(self, lat: float, lon: float, altitude_m: float) -> Tuple[bool, List[str]]:
        """Check if point is in critical airspace"""
        zones = self.query_point(lat, lon, altitude_m)
        
        critical = []
        for zone in zones:
            if zone.classification in ['A', 'B', 'Prohibited', 'Restricted']:
                critical.append(f"{zone.name} ({zone.classification})")
        
        return len(critical) > 0, critical


def load_openaip_geojson(file_path: str) -> AirspaceDatabase:
    """Load OpenAIP GeoJSON export"""
    db = AirspaceDatabase()
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        for feature in data.get('features', []):
            props = feature.get('properties', {})
            geom = feature.get('geometry', {})
            
            if geom.get('type') == 'Polygon':
                coordinates = geom.get('coordinates', [[]])[0]
                geometry = [(c[1], c[0]) for c in coordinates]  # Swap lat/lon
                
                zone = AirspaceZone(
                    id=props.get('id', f'openaip_{len(db.zones)}'),
                    name=props.get('name', 'Unknown'),
                    classification=props.get('class', 'G'),
                    floor_m_amsl=props.get('bottom_alt', 0),
                    ceiling_m_amsl=props.get('top_alt', 99999),
                    geometry_type='polygon',
                    geometry=geometry,
                    restrictions=props.get('restrictions', []),
                    active_hours=props.get('hours', 'H24'),
                    source='openaip'
                )
                
                db.zones.append(zone)
        
        logger.info(f"Loaded {len(db.zones)} zones from OpenAIP")
        
    except Exception as e:
        logger.error(f"Failed to load OpenAIP data: {e}")
    
    return db


def create_airspace_database() -> AirspaceDatabase:
    """Factory function"""
    return AirspaceDatabase()