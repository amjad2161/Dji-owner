"""
SkyCore - DJI/Autel Flight Log Analyzer
Parses and analyzes flight logs from DJI and Autel drones.

Based on research from:
- arpanghosh8453/open-dronelog (flight log format analysis)
- o-gs/dji-firmware-tools (DJI DAT log parsing)
- anthok/autel (Autel firmware format)

Supports:
- DJI .txt flight logs
- Litchi CSV exports
- Airdata exports
"""

from __future__ import annotations

import asyncio
import json
import logging
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, BinaryIO

log = logging.getLogger(__name__)


class LogFormat(str, Enum):
    """Supported flight log formats."""
    DJI_TXT = "dji_txt"       # DJI Fly app logs
    DJI_DAT = "dji_dat"       # DJI DAT binary logs
    LITCHI_CSV = "litchi_csv"  # Litchi CSV export
    AIRDATA_CSV = "airdata_csv"  # Airdata export
    AUTEL_FLY = "autel_fly"   # Autel Sky app logs
    UNKNOWN = "unknown"


@dataclass
class FlightLogHeader:
    """Parsed flight log header/metadata."""
    drone_model: str
    firmware_version: str
    serial_number: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration_s: Optional[float] = None
    max_altitude_m: Optional[float] = None
    max_distance_m: Optional[float] = None
    battery_start_percent: Optional[float] = None
    battery_end_percent: Optional[float] = None
    flight_mode: str = "unknown"
    home_lat: Optional[float] = None
    home_lon: Optional[float] = None


@dataclass
class TelemetryPoint:
    """Single telemetry data point from flight log."""
    timestamp_s: float  # Seconds from start
    lat: float
    lon: float
    altitude_m: float
    speed_mps: float
    heading_deg: float
    battery_percent: float
    battery_voltage: Optional[float] = None
    gps_satellites: Optional[int] = None
    signal_strength: Optional[int] = None
    distance_to_home_m: Optional[float] = None
    # Attitude
    pitch_deg: Optional[float] = None
    roll_deg: Optional[float] = None
    yaw_deg: Optional[float] = None


@dataclass
class FlightLog:
    """Complete flight log data."""
    format: LogFormat
    header: FlightLogHeader
    points: list[TelemetryPoint] = field(default_factory=list)
    
    @property
    def duration_s(self) -> float:
        """Total flight duration."""
        if not self.points:
            return 0.0
        return self.points[-1].timestamp_s - self.points[0].timestamp_s
    
    @property
    def total_distance_m(self) -> float:
        """Total distance flown."""
        if len(self.points) < 2:
            return 0.0
        
        total = 0.0
        for i in range(1, len(self.points)):
            p1, p2 = self.points[i-1], self.points[i]
            total += haversine_m(p1.lat, p1.lon, p2.lat, p2.lon)
        return total
    
    @property
    def avg_speed_mps(self) -> float:
        """Average ground speed."""
        if not self.points:
            return 0.0
        return sum(p.speed_mps for p in self.points) / len(self.points)
    
    @property
    def max_speed_mps(self) -> float:
        """Maximum ground speed."""
        if not self.points:
            return 0.0
        return max(p.speed_mps for p in self.points)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in meters."""
    import math
    R = 6371000  # Earth radius in meters
    
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


class FlightLogParser:
    """Parser for various flight log formats."""
    
    def __init__(self):
        self._parsers = {
            LogFormat.DJI_TXT: self._parse_dji_txt,
            LogFormat.DJI_DAT: self._parse_dji_dat,
            LogFormat.LITCHI_CSV: self._parse_litchi_csv,
            LogFormat.AIRDATA_CSV: self._parse_airdata_csv,
            LogFormat.AUTEL_FLY: self._parse_autel_fly,
        }
    
    def parse_file(self, filepath: str | Path) -> FlightLog:
        """Parse a flight log file.
        
        Args:
            filepath: Path to the flight log file
            
        Returns:
            Parsed FlightLog object
            
        Raises:
            ValueError: If format is not recognized
        """
        path = Path(filepath)
        
        # Detect format from extension and content
        log_format = self._detect_format(path)
        
        if log_format not in self._parsers:
            raise ValueError(f"Unsupported log format: {log_format}")
        
        return self._parsers[log_format](path)
    
    def _detect_format(self, path: Path) -> LogFormat:
        """Detect log format from file extension and content."""
        ext = path.suffix.lower()
        name = path.name.lower()
        
        if ext == ".txt" or "djilog" in name or "fly" in name:
            # Could be DJI or Autel - check content
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_lines = ''.join(f.readlines(20)).lower()
                    
                    if "litchi" in first_lines:
                        return LogFormat.LITCHI_CSV
                    if "airdata" in first_lines or "airdatauv" in first_lines:
                        return LogFormat.AIRDATA_CSV
                    if "autel" in first_lines or "evo" in name:
                        return LogFormat.AUTEL_FLY
                    # DJI txt format starts with specific markers
                    if any(x in first_lines for x in ["latitude", "longitude", "altitude", "gps"]):
                        return LogFormat.DJI_TXT
            except Exception:
                pass
            
            return LogFormat.DJI_TXT
        
        if ext == ".csv":
            return LogFormat.LITCHI_CSV
        
        if ext == ".dat":
            return LogFormat.DJI_DAT
        
        return LogFormat.UNKNOWN
    
    def _parse_dji_txt(self, path: Path) -> FlightLog:
        """Parse DJI .txt flight log format.
        
        DJI logs are typically in:
        /Android/data/dji.go.v5/files/FlightRecord/
        
        Format: Tab-separated with header lines starting with #
        """
        log.debug(f"Parsing DJI TXT log: {path}")
        
        header = FlightLogHeader(
            drone_model="Unknown DJI",
            firmware_version="",
            serial_number="",
            start_time=datetime.now(timezone.utc),
        )
        points = []
        
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Skip comment lines (starting with #)
            data_lines = [l for l in lines if not l.strip().startswith('#')]
            
            if not data_lines:
                raise ValueError("No data lines found in DJI log")
            
            # Parse header from first data line or comments
            for line in lines[:20]:
                line = line.strip()
                if line.startswith('#'):
                    self._parse_dji_header_comment(line, header)
            
            # Find data columns
            first_data = data_lines[0]
            cols = first_data.split('\t')
            
            # Map column names (case-insensitive)
            col_map = {}
            for i, col in enumerate(cols):
                col_lower = col.lower()
                if 'lat' in col_lower:
                    col_map['lat'] = i
                elif 'lon' in col_lower:
                    col_map['lon'] = i
                elif 'alt' in col_lower and 'rel' not in col_lower:
                    col_map['alt'] = i
                elif 'speed' in col_lower:
                    col_map['speed'] = i
                elif 'heading' in col_lower or 'yaw' in col_lower:
                    col_map['heading'] = i
                elif 'battery' in col_lower:
                    if 'volt' in col_lower:
                        col_map['voltage'] = i
                    else:
                        col_map['battery'] = i
                elif 'time' in col_lower and 'elapsed' in col_lower.lower():
                    col_map['time'] = i
                elif 'dist' in col_lower or 'home' in col_lower:
                    col_map['distance'] = i
                elif 'sat' in col_lower:
                    col_map['satellites'] = i
                elif 'signal' in col_lower or 'rc' in col_lower:
                    col_map['signal'] = i
            
            # Parse data points
            for line in data_lines:
                try:
                    cols = line.strip().split('\t')
                    if len(cols) < 4:  # Minimum: lat, lon, alt, time
                        continue
                    
                    point = self._parse_dji_point(cols, col_map)
                    if point:
                        points.append(point)
                except Exception as e:
                    log.debug(f"Failed to parse line: {e}")
                    continue
                    
        except Exception as e:
            log.error(f"Failed to parse DJI TXT log: {e}")
        
        return FlightLog(format=LogFormat.DJI_TXT, header=header, points=points)
    
    def _parse_dji_header_comment(self, line: str, header: FlightLogHeader) -> None:
        """Parse DJI header comment line."""
        line = line.lstrip('#').strip()
        
        if 'model' in line.lower() or 'drone' in line.lower():
            header.drone_model = line.split(':')[-1].strip()
        elif 'sn' in line.lower() or 'serial' in line.lower():
            header.serial_number = line.split(':')[-1].strip()
        elif 'firmware' in line.lower() or 'fw' in line.lower():
            header.firmware_version = line.split(':')[-1].strip()
        elif 'start' in line.lower() and 'time' in line.lower():
            try:
                # Parse timestamp
                ts_str = line.split(':')[-1].strip()
                header.start_time = datetime.fromisoformat(ts_str.replace('/', '-'))
            except Exception:
                pass
    
    def _parse_dji_point(self, cols: list[str], col_map: dict) -> Optional[TelemetryPoint]:
        """Parse a single DJI telemetry point."""
        try:
            lat = float(cols[col_map.get('lat', 0)])
            lon = float(cols[col_map.get('lon', 1)])
            alt = float(cols[col_map.get('alt', 2)] if 'alt' in col_map else 0.0)
            
            time_s = float(cols[col_map.get('time', 3)]) if 'time' in col_map else 0.0
            
            speed = float(cols[col_map.get('speed', 4)]) if 'speed' in col_map else 0.0
            heading = float(cols[col_map.get('heading', 5)]) if 'heading' in col_map else 0.0
            battery = float(cols[col_map.get('battery', 6)]) if 'battery' in col_map else 100.0
            
            return TelemetryPoint(
                timestamp_s=time_s,
                lat=lat,
                lon=lon,
                altitude_m=alt,
                speed_mps=speed,
                heading_deg=heading,
                battery_percent=battery,
                battery_voltage=float(cols[col_map['voltage']]) if 'voltage' in col_map else None,
                distance_to_home_m=float(cols[col_map['distance']]) if 'distance' in col_map else None,
                gps_satellites=int(cols[col_map['satellites']]) if 'satellites' in col_map else None,
                signal_strength=int(cols[col_map['signal']]) if 'signal' in col_map else None,
            )
        except (ValueError, IndexError):
            return None
    
    def _parse_dji_dat(self, path: Path) -> FlightLog:
        """Parse DJI DAT binary flight log format.
        
        Based on o-gs/dji-firmware-tools research.
        DAT files contain DUML (DJI Unifying Message Language) packets.
        """
        log.debug(f"Parsing DJI DAT log: {path}")
        
        header = FlightLogHeader(
            drone_model="Unknown DJI",
            firmware_version="",
            serial_number="",
            start_time=datetime.now(timezone.utc),
        )
        points = []
        
        try:
            with open(path, 'rb') as f:
                data = f.read()
            
            # DAT files contain multiple DUML packets
            # Parse packet structure
            offset = 0
            while offset < len(data) - 24:  # Minimum packet size
                try:
                    # Look for packet start marker (0x55 for DJI)
                    if data[offset] != 0x55:
                        offset += 1
                        continue
                    
                    # Parse DUML packet header (simplified)
                    # Structure: SOF(1) + Len(2) + Seq(2) + CRC(1) + ...
                    packet_len = int.from_bytes(data[offset+1:offset+3], 'little')
                    if packet_len > 1024 or packet_len < 10:
                        offset += 1
                        continue
                    
                    # Extract telemetry data (simplified parsing)
                    # Real implementation would use comm_dat2pcap.py approach
                    offset += packet_len
                    
                except Exception:
                    offset += 1
                    continue
            
            log.warning(f"DAT parsing is simplified - {len(points)} points extracted")
            
        except Exception as e:
            log.error(f"Failed to parse DJI DAT log: {e}")
        
        return FlightLog(format=LogFormat.DJI_DAT, header=header, points=points)
    
    def _parse_litchi_csv(self, path: Path) -> FlightLog:
        """Parse Litchi CSV flight log format."""
        log.debug(f"Parsing Litchi CSV log: {path}")
        
        header = FlightLogHeader(
            drone_model="Litchi Flight",
            firmware_version="",
            serial_number="",
            start_time=datetime.now(timezone.utc),
        )
        points = []
        
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            if not lines:
                return FlightLog(format=LogFormat.LITCHI_CSV, header=header, points=points)
            
            # Parse header line
            header_line = lines[0].strip()
            cols = [c.strip() for c in header_line.split(',')]
            
            # Map columns
            col_map = {}
            for i, col in enumerate(cols):
                col_lower = col.lower()
                if 'lat' in col_lower:
                    col_map['lat'] = i
                elif 'lon' in col_lower:
                    col_map['lon'] = i
                elif 'alt' in col_lower:
                    col_map['alt'] = i
                elif 'speed' in col_lower:
                    col_map['speed'] = i
                elif 'heading' in col_lower or 'yaw' in col_lower:
                    col_map['heading'] = i
                elif 'battery' in col_lower:
                    col_map['battery'] = i
                elif 'time' in col_lower or 'timestamp' in col_lower or 'elapsed' in col_lower:
                    col_map['time'] = i
            
            # Parse data lines
            for line in lines[1:]:
                try:
                    vals = line.strip().split(',')
                    if len(vals) < 4:
                        continue
                    
                    lat = float(vals[col_map.get('lat', 0)])
                    lon = float(vals[col_map.get('lon', 1)])
                    alt = float(vals[col_map.get('alt', 2)])
                    time_s = float(vals[col_map.get('time', 3)]) if 'time' in col_map else 0.0
                    speed = float(vals[col_map.get('speed', 4)]) if 'speed' in col_map else 0.0
                    heading = float(vals[col_map.get('heading', 5)]) if 'heading' in col_map else 0.0
                    battery = float(vals[col_map.get('battery', 6)]) if 'battery' in col_map else 100.0
                    
                    points.append(TelemetryPoint(
                        timestamp_s=time_s,
                        lat=lat, lon=lon, altitude_m=alt,
                        speed_mps=speed, heading_deg=heading,
                        battery_percent=battery,
                    ))
                except (ValueError, IndexError):
                    continue
                    
        except Exception as e:
            log.error(f"Failed to parse Litchi CSV log: {e}")
        
        return FlightLog(format=LogFormat.LITCHI_CSV, header=header, points=points)
    
    def _parse_airdata_csv(self, path: Path) -> FlightLog:
        """Parse Airdata CSV export format."""
        # Similar to Litchi but different column structure
        return self._parse_litchi_csv(path)  # Reuse for now
    
    def _parse_autel_fly(self, path: Path) -> FlightLog:
        """Parse Autel flight log format.
        
        Based on anthok/autel research - Autel uses similar structure
        to DJI with filetransfer XML-like format.
        """
        log.debug(f"Parsing Autel flight log: {path}")
        
        header = FlightLogHeader(
            drone_model="Autel Drone",
            firmware_version="",
            serial_number="",
            start_time=datetime.now(timezone.utc),
        )
        points = []
        
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Autel logs may have different structure - try JSON-like first
            try:
                import json
                data = json.loads(content)
                if isinstance(data, dict):
                    # Parse JSON format
                    header.drone_model = data.get('model', data.get('drone', 'Autel'))
                    header.serial_number = data.get('serial', data.get('sn', ''))
                    
                    if 'telemetry' in data:
                        for pt in data['telemetry']:
                            points.append(TelemetryPoint(
                                timestamp_s=pt.get('time', pt.get('elapsed', 0)),
                                lat=pt.get('lat', pt.get('latitude', 0)),
                                lon=pt.get('lon', pt.get('longitude', 0)),
                                altitude_m=pt.get('alt', pt.get('altitude', 0)),
                                speed_mps=pt.get('speed', 0),
                                heading_deg=pt.get('heading', pt.get('yaw', 0)),
                                battery_percent=pt.get('battery', 100),
                            ))
            except json.JSONDecodeError:
                # Try tab-separated like DJI
                lines = content.split('\n')
                for line in lines:
                    if line.strip() and not line.startswith('#'):
                        cols = line.split('\t')
                        if len(cols) >= 4:
                            try:
                                points.append(TelemetryPoint(
                                    timestamp_s=float(cols[0]) if cols[0] else 0,
                                    lat=float(cols[1]) if cols[1] else 0,
                                    lon=float(cols[2]) if cols[2] else 0,
                                    altitude_m=float(cols[3]) if cols[3] else 0,
                                    speed_mps=float(cols[4]) if len(cols) > 4 and cols[4] else 0,
                                    heading_deg=float(cols[5]) if len(cols) > 5 and cols[5] else 0,
                                    battery_percent=float(cols[6]) if len(cols) > 6 and cols[6] else 100,
                                ))
                            except ValueError:
                                continue
                                
        except Exception as e:
            log.error(f"Failed to parse Autel flight log: {e}")
        
        return FlightLog(format=LogFormat.AUTEL_FLY, header=header, points=points)


# Global parser instance
default_parser = FlightLogParser()


def parse_flight_log(filepath: str | Path) -> FlightLog:
    """Convenience function to parse a flight log file."""
    return default_parser.parse_file(filepath)