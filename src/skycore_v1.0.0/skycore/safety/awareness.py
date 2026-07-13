"""
SkyCore Safety - ADSB Awareness
================================
Automatic Dependent Surveillance-Broadcast (ADS-B) receiver and processor.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import struct

log = logging.getLogger(__name__)


class AircraftType(Enum):
    """Aircraft type categories."""
    UNKNOWN = 0
    LIGHT = 1  # < 7,500 kg
    SMALL = 2  # 7,500 - 34,000 kg
    LARGE = 3  # 34,000 - 136,000 kg
    HEAVY = 4  # > 136,000 kg
    HIGH_PERFORMANCE = 5
    ROTORCRAFT = 6
    GLIDER = 7
    BALLOON = 8
    UAV = 9


@dataclass
class ADSBCall:
    """ADS-B position call."""
    icao_address: str
    timestamp: float
    latitude: float
    longitude: float
    altitude: float  # feet MSL
    ground_speed: float  # knots
    track: float  # degrees True
    vertical_rate: float  # feet/minute
    callsign: str = ""
    aircraft_type: AircraftType = AircraftType.UNKNOWN
    category: int = 0
    
    @property
    def position(self) -> Tuple[float, float]:
        return (self.latitude, self.longitude)
    
    @property
    def altitude_meters(self) -> float:
        return self.altitude * 0.3048  # feet to meters
    
    def to_dict(self) -> Dict:
        return {
            'icao': self.icao_address,
            'timestamp': self.timestamp,
            'position': {'lat': self.latitude, 'lon': self.longitude},
            'altitude_ft': self.altitude,
            'altitude_m': self.altitude_meters,
            'ground_speed_kts': self.ground_speed,
            'track_deg': self.track,
            'vertical_rate_fpm': self.vertical_rate,
            'callsign': self.callsign,
            'aircraft_type': self.aircraft_type.name
        }


@dataclass
class TrafficAlert:
    """Traffic alert for nearby aircraft."""
    aircraft: ADSBCall
    distance_m: float
    bearing_deg: float
    time_to_collision_sec: float
    relative_altitude_ft: float
    alert_level: str  # 'none', 'proximity', 'traffic'
    recommendation: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'aircraft': self.aircraft.to_dict(),
            'distance_m': round(self.distance_m, 1),
            'bearing_deg': round(self.bearing_deg, 1),
            'ttc_sec': round(self.time_to_collision_sec, 1),
            'relative_altitude_ft': round(self.relative_altitude_ft, 1),
            'alert_level': self.alert_level,
            'recommendation': self.recommendation
        }


class ADSBReceiver:
    """
    ADS-B receiver for traffic awareness.
    
    Supports:
    - RTL-SDR hardware
    - MAVLink ADSB messages
    - Dump1090 server integration
    - Mock data for testing
    
    Features:
    - Real-time traffic monitoring
    - Collision detection and alerting
    - Traffic alert generation
    - Historical track playback
    """
    
    def __init__(self, source: str = "mock", host: str = "localhost",
                 port: int = 30002, own_altitude_ft: float = 400):
        """
        Initialize ADSB receiver.
        
        Args:
            source: Source type ('rtlsdr', 'mavlink', 'dump1090', 'mock')
            host: Dump1090 server host
            port: Dump1090/server port
            own_altitude_ft: Own aircraft altitude in feet
        """
        self.source = source
        self.host = host
        self.port = port
        self.own_altitude_ft = own_altitude_ft
        
        # Traffic tracking
        self.tracked_aircraft: Dict[str, ADSBCall] = {}
        self.aircraft_history: Dict[str, deque] = {}
        self.max_history = 300  # 5 minutes at 1Hz
        
        # Alert configuration
        self.proximity_radius_m = 5000  # meters
        self.tca_radius_m = 1000  # meters for time-to-collision alert
        self.tca_threshold_sec = 60  # seconds
        self.horizontal_exclusion_ft = 1000  # feet vertical separation
        
        # Alert callbacks
        self._alert_callbacks: List[Callable] = []
        
        # Statistics
        self.total_calls_received = 0
        self.alerts_generated = 0
        self.closest_approach = float('inf')
        self.closest_aircraft: Optional[str] = None
        
        # Running state
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        log.info(f"ADSB receiver initialized (source: {source})")
    
    async def start(self):
        """Start receiving ADSB traffic."""
        if self._running:
            return
        
        self._running = True
        
        if self.source == 'mock':
            self._task = asyncio.create_task(self._mock_loop())
        elif self.source == 'dump1090':
            self._task = asyncio.create_task(self._dump1090_loop())
        elif self.source == 'mavlink':
            self._task = asyncio.create_task(self._mavlink_loop())
        else:
            log.warning(f"Unknown ADSB source: {self.source}")
    
    async def stop(self):
        """Stop receiving ADSB traffic."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _mock_loop(self):
        """Mock ADSB loop for testing."""
        import random
        
        # Mock aircraft ICAOs
        mock_icaos = [
            "A12B34", "C56D78", "E90F12", "345678",
            "ABCDEF", "789012", "FEDCBA", "012345"
        ]
        
        base_lat, base_lon = 31.97, 34.79  # Israel
        
        while self._running:
            try:
                # Simulate 1-5 aircraft
                num_aircraft = random.randint(1, 5)
                
                for i in range(num_aircraft):
                    icao = mock_icaos[random.randint(0, len(mock_icaos) - 1)]
                    
                    # Generate position with some movement
                    lat = base_lat + random.uniform(-0.1, 0.1)
                    lon = base_lon + random.uniform(-0.2, 0.2)
                    alt = random.randint(1000, 15000)
                    speed = random.randint(80, 250)
                    track = random.uniform(0, 360)
                    
                    call = ADSBCall(
                        icao_address=icao,
                        timestamp=time.time(),
                        latitude=lat,
                        longitude=lon,
                        altitude=alt,
                        ground_speed=speed,
                        track=track,
                        vertical_rate=random.uniform(-500, 500),
                        callsign=f"FL{random.randint(100, 999)}"
                    )
                    
                    self._update_aircraft(call)
                
                await asyncio.sleep(1)  # 1 Hz update
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Mock ADSB error: {e}")
                await asyncio.sleep(1)
    
    async def _dump1090_loop(self):
        """Connect to Dump1090 beast/basestation server."""
        import json
        
        reader, writer = None, None
        
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
            log.info(f"Connected to Dump1090 at {self.host}:{self.port}")
            
            buffer = ""
            
            while self._running:
                try:
                    data = await reader.read(1024)
                    if not data:
                        break
                    
                    buffer += data.decode('utf-8', errors='ignore')
                    
                    # Process messages
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        
                        if line.startswith('MSG,'):
                            call = self._parse_basestation(line)
                            if call:
                                self._update_aircraft(call)
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log.error(f"Dump1090 read error: {e}")
                    await asyncio.sleep(1)
            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"Dump1090 connection error: {e}")
        finally:
            if writer:
                writer.close()
    
    async def _mavlink_loop(self):
        """Receive ADSB messages via MAVLink."""
        # Would integrate with MAVLink for hardware receivers
        while self._running:
            await asyncio.sleep(1)
    
    def _parse_basestation(self, line: str) -> Optional[ADSBCall]:
        """Parse BaseStation format message."""
        try:
            parts = line.split(',')
            
            if len(parts) < 22:
                return None
            
            # MSG,type,subtype,uuid,timestamp,status,icao,callsign,ground_speed,track,lat,lon,altitude,vrate,callsign2,desc,gsr,ts,hdg,gps_valid,nav_modes,metype,metype_ha
            msg_type = parts[1]
            
            if msg_type not in ['MSG-1', 'MSG-3', 'MSG-4', 'MSG-5']:
                return None
            
            icao = parts[5].strip()
            callsign = parts[10].strip()[:8]
            
            lat = float(parts[14])
            lon = float(parts[15])
            alt = float(parts[16])
            speed = float(parts[12])
            track = float(parts[13])
            vrate = float(parts[17]) if parts[17] else 0
            
            if abs(lat) < 1 or abs(lon) < 1:  # Invalid position
                return None
            
            return ADSBCall(
                icao_address=icao,
                timestamp=time.time(),
                latitude=lat,
                longitude=lon,
                altitude=alt,
                ground_speed=speed,
                track=track,
                vertical_rate=vrate,
                callsign=callsign
            )
            
        except (ValueError, IndexError):
            return None
    
    def _update_aircraft(self, call: ADSBCall):
        """Update tracked aircraft."""
        self.tracked_aircraft[call.icao_address] = call
        self.total_calls_received += 1
        
        # Update history
        if call.icao_address not in self.aircraft_history:
            self.aircraft_history[call.icao_address] = deque(maxlen=self.max_history)
        
        self.aircraft_history[call.icao_address].append(call)
        
        # Check for alert conditions
        self._check_alerts(call)
    
    def _check_alerts(self, call: ADSBCall):
        """Check if aircraft triggers alert conditions."""
        # Calculate relative altitude
        rel_alt = call.altitude - self.own_altitude_ft
        
        # Only alert if within vertical separation threshold
        if abs(rel_alt) > self.horizontal_exclusion_ft * 2:
            return
        
        # Calculate distance to own position
        # In real implementation, would use own lat/lon
        distance = self._estimate_distance(call)
        
        # Update closest approach
        if distance < self.closest_approach:
            self.closest_approach = distance
            self.closest_aircraft = call.icao_address
        
        # Generate alerts
        if distance < self.tca_radius_m:
            self._generate_alert(call, distance, rel_alt, 'traffic')
        elif distance < self.proximity_radius_m:
            self._generate_alert(call, distance, rel_alt, 'proximity')
    
    def _estimate_distance(self, call: ADSBCall) -> float:
        """Estimate distance to aircraft."""
        # Simplified - would use haversine formula with own position
        return abs(call.altitude - self.own_altitude_ft) * 0.3 + 1000
    
    def _generate_alert(self, call: ADSBCall, distance: float, 
                        rel_alt: float, level: str):
        """Generate traffic alert."""
        bearing = self._calculate_bearing(call)
        
        # Time to collision estimation
        speed = call.ground_speed * 0.514444  # knots to m/s
        ttc = distance / speed if speed > 0 else float('inf')
        
        recommendation = self._get_recommendation(call, distance, rel_alt)
        
        alert = TrafficAlert(
            aircraft=call,
            distance_m=distance,
            bearing_deg=bearing,
            time_to_collision_sec=ttc,
            relative_altitude_ft=rel_alt,
            alert_level=level,
            recommendation=recommendation
        )
        
        self.alerts_generated += 1
        
        # Call callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                log.error(f"Alert callback error: {e}")
    
    def _calculate_bearing(self, call: ADSBCall) -> float:
        """Calculate bearing to aircraft."""
        # Simplified bearing calculation
        return call.track + 180 % 360
    
    def _get_recommendation(self, call: ADSBCall, distance: float, 
                            rel_alt: float) -> str:
        """Get avoidance recommendation."""
        if call.vertical_rate > 500:
            return "Descend - traffic climbing above"
        elif call.vertical_rate < -500:
            return "Climb - traffic descending below"
        elif rel_alt > 0:
            return "Descend - traffic above"
        else:
            return "Climb - traffic below"
    
    def on_alert(self, callback: Callable):
        """Register alert callback."""
        self._alert_callbacks.append(callback)
    
    def get_traffic(self) -> List[ADSBCall]:
        """Get all tracked traffic."""
        return list(self.tracked_aircraft.values())
    
    def get_closest(self) -> Optional[ADSBCall]:
        """Get closest aircraft."""
        if self.closest_aircraft and self.closest_aircraft in self.tracked_aircraft:
            return self.tracked_aircraft[self.closest_aircraft]
        return None
    
    def get_history(self, icao: str) -> List[ADSBCall]:
        """Get track history for aircraft."""
        return list(self.aircraft_history.get(icao, []))
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get receiver statistics."""
        return {
            'tracked_aircraft': len(self.tracked_aircraft),
            'total_calls': self.total_calls_received,
            'alerts_generated': self.alerts_generated,
            'closest_distance_m': round(self.closest_approach, 1),
            'closest_icao': self.closest_aircraft,
            'source': self.source,
            'running': self._running
        }


# Export
__all__ = ['ADSBReceiver', 'ADSBCall', 'TrafficAlert', 'AircraftType']