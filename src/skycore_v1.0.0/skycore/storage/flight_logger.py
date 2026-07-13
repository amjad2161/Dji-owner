"""
SkyCore Storage - Flight Logger
===============================
Flight data logging and telemetry recording.
"""

import asyncio
import logging
import json
import time
import os
from typing import Dict, List, Optional, Any, Callable, Deque
from dataclasses import dataclass, field, asdict
from collections import deque
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class TelemetryPoint:
    """Single telemetry data point."""
    timestamp: float
    lat: float
    lon: float
    alt: float  # meters
    vx: float = 0.0  # velocity north
    vy: float = 0.0  # velocity east
    vz: float = 0.0  # velocity down
    roll: float = 0.0  # degrees
    pitch: float = 0.0
    yaw: float = 0.0
    battery_percent: float = 100.0
    battery_voltage: float = 0.0
    battery_current: float = 0.0
    gps_sats: int = 0
    gps_hdop: float = 99.0
    rtk_status: str = "none"
    signal_quality: float = 100.0
    temperature: float = 25.0
    motor_rpm: List[int] = field(default_factory=lambda: [0, 0, 0, 0])
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'position': {'lat': self.lat, 'lon': self.lon, 'alt': self.alt},
            'velocity': {'vx': self.vx, 'vy': self.vy, 'vz': self.vz},
            'attitude': {'roll': self.roll, 'pitch': self.pitch, 'yaw': self.yaw},
            'battery': {
                'percent': self.battery_percent,
                'voltage': self.battery_voltage,
                'current': self.battery_current
            },
            'gps': {'sats': self.gps_sats, 'hdop': self.gps_hdop, 'rtk': self.rtk_status},
            'signal': self.signal_quality,
            'temperature': self.temperature,
            'motors': self.motor_rpm
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TelemetryPoint':
        pos = data.get('position', {})
        vel = data.get('velocity', {})
        att = data.get('attitude', {})
        bat = data.get('battery', {})
        gps = data.get('gps', {})
        
        return cls(
            timestamp=data.get('timestamp', 0),
            lat=pos.get('lat', 0),
            lon=pos.get('lon', 0),
            alt=pos.get('alt', 0),
            vx=vel.get('vx', 0),
            vy=vel.get('vy', 0),
            vz=vel.get('vz', 0),
            roll=att.get('roll', 0),
            pitch=att.get('pitch', 0),
            yaw=att.get('yaw', 0),
            battery_percent=bat.get('percent', 100),
            battery_voltage=bat.get('voltage', 0),
            battery_current=bat.get('current', 0),
            gps_sats=gps.get('sats', 0),
            gps_hdop=gps.get('hdop', 99),
            rtk_status=gps.get('rtk', 'none'),
            signal_quality=data.get('signal', 100),
            temperature=data.get('temperature', 25),
            motor_rpm=data.get('motors', [0, 0, 0, 0])
        )


@dataclass
class FlightEvent:
    """Flight event log entry."""
    timestamp: float
    event_type: str
    severity: str  # info, warning, error, critical
    description: str
    data: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'type': self.event_type,
            'severity': self.severity,
            'description': self.description,
            'data': self.data
        }


class FlightLogger:
    """
    Real-time flight data logger.
    
    Records telemetry data and events to file with
    buffering and async writing.
    
    Features:
    - Real-time telemetry logging
    - Event recording
    - Buffered async writes
    - Multiple output formats
    - Automatic file rotation
    """
    
    def __init__(self, log_dir: str = "./flight_logs", 
                 buffer_size: int = 100,
                 write_interval_sec: float = 5.0):
        """
        Initialize flight logger.
        
        Args:
            log_dir: Directory for flight logs
            buffer_size: Number of points to buffer before write
            write_interval_sec: Maximum interval between writes
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.buffer_size = buffer_size
        self.write_interval = write_interval_sec
        
        # Telemetry buffer
        self._telemetry_buffer: Deque[TelemetryPoint] = deque(maxlen=buffer_size * 10)
        
        # Event buffer
        self._event_buffer: Deque[FlightEvent] = deque(maxlen=1000)
        
        # Current flight
        self._current_flight_id: Optional[str] = None
        self._current_telemetry_file: Optional[str] = None
        self._current_events_file: Optional[str] = None
        
        # Statistics
        self.total_points_logged = 0
        self.total_events_logged = 0
        self.total_flights = 0
        
        # Running state
        self._running = False
        self._write_task: Optional[asyncio.Task] = None
        
        log.info(f"Flight logger initialized: {log_dir}")
    
    async def start_flight(self, flight_id: Optional[str] = None) -> str:
        """
        Start logging a new flight.
        
        Args:
            flight_id: Optional flight ID (generated if not provided)
            
        Returns:
            Flight ID
        """
        if self._running:
            await self.stop_flight()
        
        if not flight_id:
            flight_id = f"flight_{int(time.time())}"
        
        self._current_flight_id = flight_id
        
        # Create log files
        timestamp = int(time.time())
        self._current_telemetry_file = str(self.log_dir / f"{flight_id}_telemetry.json")
        self._current_events_file = str(self.log_dir / f"{flight_id}_events.json")
        
        # Initialize files with metadata
        with open(self._current_telemetry_file, 'w') as f:
            json.dump({
                'flight_id': flight_id,
                'start_time': time.time(),
                'format_version': '1.0'
            }, f)
            f.write('\n')  # One JSON per line format
        
        with open(self._current_events_file, 'w') as f:
            json.dump({
                'flight_id': flight_id,
                'start_time': time.time(),
                'events': []
            }, f)
        
        self._running = True
        self._write_task = asyncio.create_task(self._write_loop())
        
        log.info(f"Flight logging started: {flight_id}")
        
        return flight_id
    
    async def stop_flight(self) -> Optional[Dict]:
        """
        Stop logging current flight.
        
        Returns:
            Flight summary dictionary
        """
        if not self._running:
            return None
        
        self._running = False
        
        # Wait for write task to complete
        if self._write_task:
            try:
                await asyncio.wait_for(self._write_task, timeout=5.0)
            except asyncio.TimeoutError:
                pass
        
        # Flush remaining data
        await self._flush_buffers()
        
        # Update end time in files
        if self._current_telemetry_file and os.path.exists(self._current_telemetry_file):
            # Add end marker
            with open(self._current_telemetry_file, 'a') as f:
                json.dump({
                    'flight_id': self._current_flight_id,
                    'end_time': time.time(),
                    'type': 'flight_end'
                }, f)
                f.write('\n')
        
        # Calculate summary
        summary = {
            'flight_id': self._current_flight_id,
            'telemetry_points': self.total_points_logged,
            'events': self.total_events_logged,
            'start_time': 0,
            'end_time': time.time()
        }
        
        self.total_flights += 1
        self._current_flight_id = None
        self._current_telemetry_file = None
        self._current_events_file = None
        
        log.info(f"Flight logging stopped: {summary}")
        
        return summary
    
    async def log_telemetry(self, telemetry: Dict):
        """
        Log telemetry data point.
        
        Args:
            telemetry: Telemetry dictionary from drone
        """
        if not self._running:
            return
        
        # Create telemetry point
        point = self._parse_telemetry(telemetry)
        
        self._telemetry_buffer.append(point)
        self.total_points_logged += 1
        
        # Check if buffer needs flushing
        if len(self._telemetry_buffer) >= self.buffer_size:
            await self._flush_telemetry_buffer()
    
    async def log_event(self, event_type: str, description: str, 
                       severity: str = "info", data: Optional[Dict] = None):
        """
        Log flight event.
        
        Args:
            event_type: Event type (takeoff, land, warning, etc.)
            description: Event description
            severity: Event severity (info, warning, error, critical)
            data: Additional event data
        """
        if not self._running:
            return
        
        event = FlightEvent(
            timestamp=time.time(),
            event_type=event_type,
            severity=severity,
            description=description,
            data=data or {}
        )
        
        self._event_buffer.append(event)
        self.total_events_logged += 1
        
        if len(self._event_buffer) >= 50:
            await self._flush_event_buffer()
    
    def _parse_telemetry(self, telemetry: Dict) -> TelemetryPoint:
        """Parse telemetry dictionary to TelemetryPoint."""
        return TelemetryPoint(
            timestamp=telemetry.get('timestamp', time.time()),
            lat=telemetry.get('lat', 0),
            lon=telemetry.get('lon', 0),
            alt=telemetry.get('alt', 0),
            vx=telemetry.get('vx', 0),
            vy=telemetry.get('vy', 0),
            vz=telemetry.get('vz', 0),
            roll=telemetry.get('roll', 0),
            pitch=telemetry.get('pitch', 0),
            yaw=telemetry.get('yaw', 0),
            battery_percent=telemetry.get('battery_percent', 100),
            battery_voltage=telemetry.get('battery_voltage', 0),
            battery_current=telemetry.get('battery_current', 0),
            gps_sats=telemetry.get('gps_sats', 0),
            gps_hdop=telemetry.get('gps_hdop', 99),
            rtk_status=telemetry.get('rtk_status', 'none'),
            signal_quality=telemetry.get('signal_quality', 100),
            temperature=telemetry.get('temperature', 25),
            motor_rpm=telemetry.get('motor_rpm', [0, 0, 0, 0])
        )
    
    async def _write_loop(self):
        """Background write loop."""
        while self._running:
            try:
                await asyncio.sleep(self.write_interval)
                await self._flush_buffers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Write loop error: {e}")
    
    async def _flush_buffers(self):
        """Flush all buffers to disk."""
        await self._flush_telemetry_buffer()
        await self._flush_event_buffer()
    
    async def _flush_telemetry_buffer(self):
        """Flush telemetry buffer to file."""
        if not self._current_telemetry_file or not self._telemetry_buffer:
            return
        
        try:
            with open(self._current_telemetry_file, 'a') as f:
                while self._telemetry_buffer:
                    point = self._telemetry_buffer.popleft()
                    f.write(json.dumps(point.to_dict()) + '\n')
        except Exception as e:
            log.error(f"Telemetry flush error: {e}")
    
    async def _flush_event_buffer(self):
        """Flush event buffer to file."""
        if not self._current_events_file or not self._event_buffer:
            return
        
        try:
            with open(self._current_events_file, 'a') as f:
                while self._event_buffer:
                    event = self._event_buffer.popleft()
                    f.write(json.dumps(event.to_dict()) + '\n')
        except Exception as e:
            log.error(f"Event flush error: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get logger statistics."""
        return {
            'current_flight': self._current_flight_id,
            'total_points': self.total_points_logged,
            'total_events': self.total_events_logged,
            'total_flights': self.total_flights,
            'buffer_size': len(self._telemetry_buffer),
            'running': self._running
        }
    
    def get_log_files(self, flight_id: Optional[str] = None) -> Dict[str, Optional[str]]:
        """Get log files for flight."""
        if flight_id:
            return {
                'telemetry': str(self.log_dir / f"{flight_id}_telemetry.json"),
                'events': str(self.log_dir / f"{flight_id}_events.json")
            }
        elif self._current_flight_id:
            return {
                'telemetry': self._current_telemetry_file,
                'events': self._current_events_file
            }
        return {'telemetry': None, 'events': None}


# Export
__all__ = ['FlightLogger', 'TelemetryPoint', 'FlightEvent']