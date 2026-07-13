"""OpenSky Network API integration for airspace awareness.

Implements:
- OpenSky REST API client
- Flight data retrieval
- Bounding box queries
- Aircraft state vector processing
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
import time
import urllib.request
import json


@dataclass
class OpenSkyConfig:
    """OpenSky API configuration."""
    base_url: str = "https://opensky-network.org/api"
    
    # Authentication (optional for public data)
    username: Optional[str] = None
    password: Optional[str] = None
    
    # Request settings
    timeout: float = 10.0
    max_results: int = 1000
    
    # Caching
    cache_duration: float = 5.0  # seconds


@dataclass
class FlightState:
    """Single aircraft state vector."""
    icao24: str              # ICAO24 address (hex)
    callsign: str           # Flight callsign
    origin_country: str      # Country of origin
    
    # Position
    latitude: float
    longitude: float
    altitude: float          # meters barometric
    geo_altitude: float      # meters geometric
    
    # Motion
    velocity: float          # m/s
    heading: float           # degrees (0-360)
    
    # Time
    last_contact: float      # Unix timestamp
    time_position: float
    
    # Status
    on_ground: bool
    spoofed: bool
    
    # Velocity components
    vertical_rate: float     # m/s
    velocity_vnorth: float
    velocity_veast: float


class OpenSkyClient:
    """OpenSky Network API client."""
    
    def __init__(self, config: Optional[OpenSkyConfig] = None):
        self.config = config or OpenSkyConfig()
        
        # Cache
        self._cache: Dict[str, Tuple[float, any]] = {}
        
        # Request counter
        self.requests_today = 0
        self.last_request_time = 0
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make HTTP request to OpenSky API.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            Response JSON or None
        """
        url = f"{self.config.base_url}/{endpoint}"
        
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"
        
        # Create request with optional auth
        req = urllib.request.Request(url)
        
        if self.config.username:
            import base64
            credentials = f"{self.config.username}:{self.config.password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            req.add_header('Authorization', f'Basic {encoded}')
        
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                data = json.loads(response.read().decode())
                self.requests_today += 1
                self.last_request_time = time.time()
                return data
        except Exception as e:
            print(f"OpenSky API error: {e}")
            return None
    
    def get_states(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None
    ) -> List[FlightState]:
        """Get all aircraft states within bounding box.
        
        Args:
            bbox: (lamin, lomin, lamax, lomax) degrees
            
        Returns:
            List of FlightState objects
        """
        # Check cache
        cache_key = f"states_{bbox}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self.config.cache_duration:
                return cached_data
        
        # Build params
        params = {}
        
        if bbox:
            params['lamin'] = bbox[0]
            params['lomin'] = bbox[1]
            params['lamax'] = bbox[2]
            params['lomax'] = bbox[3]
        
        # Make request
        response = self._make_request("states/all", params)
        
        if not response or 'states' not in response:
            return []
        
        # Parse states
        states = []
        
        for state_array in response['states']:
            if state_array is None:
                continue
            
            try:
                state = self._parse_state(state_array)
                states.append(state)
            except Exception as e:
                print(f"Error parsing state: {e}")
                continue
        
        # Update cache
        self._cache[cache_key] = (time.time(), states)
        
        return states
    
    def _parse_state(self, state_array: List) -> FlightState:
        """Parse state array into FlightState object."""
        return FlightState(
            icao24=state_array[0] or "",
            callsign=state_array[1] or "",
            origin_country=state_array[2] or "",
            latitude=float(state_array[3]) if state_array[3] else 0.0,
            longitude=float(state_array[4]) if state_array[4] else 0.0,
            altitude=float(state_array[5]) if state_array[5] else 0.0,
            geo_altitude=float(state_array[6]) if state_array[6] else 0.0,
            on_ground=bool(state_array[8]) if len(state_array) > 8 else False,
            velocity=float(state_array[9]) if state_array[9] else 0.0,
            heading=float(state_array[10]) if state_array[10] else 0.0,
            vertical_rate=float(state_array[11]) if state_array[11] else 0.0,
            time_position=float(state_array[12]) if state_array[12] else 0.0,
            last_contact=float(state_array[13]) if state_array[13] else 0.0,
            spoofed=bool(state_array[14]) if len(state_array) > 14 else False,
            velocity_vnorth=0.0,
            velocity_veast=0.0
        )
    
    def get_states_by_callsign(
        self,
        callsign_pattern: str
    ) -> List[FlightState]:
        """Get aircraft by callsign pattern.
        
        Args:
            callsign_pattern: Callsign to search (supports wildcards)
            
        Returns:
            List of matching FlightState objects
        """
        # Get all states (OpenSky doesn't support callsign filter directly)
        all_states = self.get_states()
        
        # Filter by callsign
        pattern = callsign_pattern.upper().replace('*', '.*')
        import re
        regex = re.compile(pattern)
        
        return [s for s in all_states if regex.match(s.callsign or "")]
    
    def check_airspace_conflict(
        self,
        drone_position: Tuple[float, float, float],
        drone_radius: float = 1.0,
        altitude_buffer: float = 50.0,
        time_ahead: float = 60.0
    ) -> List[FlightState]:
        """Check for potential conflicts with manned aircraft.
        
        Args:
            drone_position: (lat, lon, alt) of drone
            drone_radius: Horizontal separation buffer (meters)
            altitude_buffer: Vertical separation buffer (meters)
            time_ahead: How far ahead to check (seconds)
            
        Returns:
            List of potentially conflicting aircraft
        """
        lat, lon, alt = drone_position
        
        # Create bounding box around drone
        lat_range = max(0.01, drone_radius / 111000)  # ~111km per degree
        lon_range = lat_range / np.cos(np.radians(lat))
        
        bbox = (
            lat - lat_range,
            lon - lon_range,
            lat + lat_range,
            lon + lon_range
        )
        
        # Get aircraft in area
        nearby = self.get_states(bbox)
        
        conflicts = []
        
        for aircraft in nearby:
            if aircraft.on_ground:
                continue
            
            # Check altitude
            alt_diff = abs(aircraft.geo_altitude - alt)
            
            if alt_diff > altitude_buffer:
                continue
            
            # Check horizontal distance
            distance = self._haversine_distance(
                lat, lon,
                aircraft.latitude, aircraft.longitude
            )
            
            if distance > drone_radius:
                continue
            
            # Estimate time to closest approach
            if aircraft.velocity > 0:
                # Simplified: assume direct approach
                closure_rate = aircraft.velocity  # m/s
                
                if closure_rate > 0:
                    tca = distance / closure_rate
                    
                    if tca < time_ahead:
                        conflicts.append(aircraft)
            else:
                # Stationary aircraft (helicopter?)
                if distance < drone_radius:
                    conflicts.append(aircraft)
        
        return conflicts
    
    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """Calculate great-circle distance between two points."""
        R = 6371000  # Earth radius in meters
        
        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)
        
        a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        
        return R * c
    
    def get_aircraft_in_region(
        self,
        center: Tuple[float, float],
        radius_km: float
    ) -> List[FlightState]:
        """Get all aircraft within radius of center point.
        
        Args:
            center: (lat, lon) center point
            radius_km: Search radius in kilometers
            
        Returns:
            List of FlightState objects
        """
        lat, lon = center
        
        # Convert km to degrees
        lat_range = radius_km / 111.0
        lon_range = radius_km / (111.0 * np.cos(np.radians(lat)))
        
        bbox = (
            lat - lat_range,
            lon - lon_range,
            lat + lat_range,
            lon + lon_range
        )
        
        # Get states in bbox
        all_states = self.get_states(bbox)
        
        # Filter by distance
        in_range = []
        for state in all_states:
            distance = self._haversine_distance(
                lat, lon,
                state.latitude, state.longitude
            ) / 1000  # Convert to km
            
            if distance <= radius_km:
                in_range.append(state)
        
        return in_range
    
    def get_statistics(self) -> Dict:
        """Get API usage statistics."""
        return {
            'requests_today': self.requests_today,
            'last_request': self.last_request_time,
            'cache_size': len(self._cache)
        }


def demo_opensky():
    """Demonstrate OpenSky API integration."""
    print("=" * 60)
    print("OpenSky Network API Demo")
    print("=" * 60)
    
    # Create client
    config = OpenSkyConfig()
    client = OpenSkyClient(config)
    
    # Query aircraft in Israel region
    print("\nQuerying aircraft in Israel region...")
    
    # Israel bounding box (approximate)
    israel_bbox = (29.5, 34.2, 33.5, 36.0)
    
    # Note: In real usage, this would make actual API calls
    # For demo, simulate response
    print(f"  Bounding box: {israel_bbox}")
    
    # Demonstrate conflict detection
    print("\n" + "=" * 40)
    print("Conflict Detection")
    print("=" * 40)
    
    drone_pos = (32.0853, 34.7818, 50)  # Tel Aviv, 50m
    
    print(f"  Drone position: lat={drone_pos[0]:.4f}, lon={drone_pos[1]:.4f}, alt={drone_pos[2]:.1f}m")
    print("  Note: Add your OpenSky credentials for live data")
    
    # Example conflict check (would use real API data)
    print("\n  To enable live data:")
    print("  1. Create OpenSky account at opensky-network.org")
    print("  2. Set config.username and config.password")
    print("  3. Uncomment API calls in code")
    
    # Demonstrate API structure
    print("\n" + "=" * 40)
    print("API Methods Available")
    print("=" * 40)
    
    print("  get_states(bbox)           - Get all aircraft in bounding box")
    print("  get_states_by_callsign()   - Search by flight callsign")
    print("  check_airspace_conflict()  - Check for conflicts with drone")
    print("  get_aircraft_in_region()   - Get aircraft within radius")


if __name__ == "__main__":
    demo_opensky()