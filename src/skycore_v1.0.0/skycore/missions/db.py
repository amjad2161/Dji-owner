"""
SkyCore Missions - Database
===========================
Mission storage and management with SQLite backend.
"""

import sqlite3
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)


@dataclass
class Mission:
    """Mission data model."""
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    mission_type: str = "custom"  # orbit, survey, inspection, search, custom
    waypoints: List[Dict] = field(default_factory=list)
    parameters: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    status: str = "draft"  # draft, ready, running, completed, aborted
    flight_count: int = 0
    total_flight_time_sec: float = 0.0
    tags: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'mission_type': self.mission_type,
            'waypoints': self.waypoints,
            'parameters': self.parameters,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'status': self.status,
            'flight_count': self.flight_count,
            'total_flight_time_sec': self.total_flight_time_sec,
            'tags': self.tags,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Mission':
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            description=data.get('description', ''),
            mission_type=data.get('mission_type', 'custom'),
            waypoints=data.get('waypoints', []),
            parameters=data.get('parameters', {}),
            created_at=data.get('created_at', time.time()),
            updated_at=data.get('updated_at', time.time()),
            status=data.get('status', 'draft'),
            flight_count=data.get('flight_count', 0),
            total_flight_time_sec=data.get('total_flight_time_sec', 0.0),
            tags=data.get('tags', []),
            metadata=data.get('metadata', {})
        )


@dataclass
class FlightLog:
    """Flight log entry."""
    id: Optional[int] = None
    mission_id: Optional[int] = None
    start_time: float = 0.0
    end_time: float = 0.0
    duration_sec: float = 0.0
    start_lat: float = 0.0
    start_lon: float = 0.0
    end_lat: float = 0.0
    end_lon: float = 0.0
    max_altitude_m: float = 0.0
    max_distance_m: float = 0.0
    battery_start: float = 100.0
    battery_end: float = 0.0
    telemetry_data: str = ""  # JSON string
    events: str = ""  # JSON string
    status: str = "unknown"  # success, aborted, failed
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'mission_id': self.mission_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_sec': self.duration_sec,
            'start_position': {'lat': self.start_lat, 'lon': self.start_lon},
            'end_position': {'lat': self.end_lat, 'lon': self.end_lon},
            'max_altitude_m': self.max_altitude_m,
            'max_distance_m': self.max_distance_m,
            'battery_start': self.battery_start,
            'battery_end': self.battery_end,
            'status': self.status
        }


class MissionDatabase:
    """
    Mission database for storing and managing missions and flight logs.
    
    SQLite-based storage with mission CRUD operations and flight tracking.
    
    Features:
    - Mission CRUD with full metadata
    - Flight log tracking
    - Search and filtering
    - Export/import functionality
    """
    
    def __init__(self, db_path: str = "skycore_missions.db"):
        """
        Initialize mission database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        
        self._init_database()
        log.info(f"Mission database initialized: {db_path}")
    
    def _init_database(self):
        """Initialize database schema."""
        conn = self._get_connection()
        
        # Missions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS missions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                mission_type TEXT DEFAULT 'custom',
                waypoints TEXT,
                parameters TEXT,
                created_at REAL,
                updated_at REAL,
                status TEXT DEFAULT 'draft',
                flight_count INTEGER DEFAULT 0,
                total_flight_time_sec REAL DEFAULT 0,
                tags TEXT,
                metadata TEXT
            )
        """)
        
        # Flight logs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flight_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id INTEGER,
                start_time REAL,
                end_time REAL,
                duration_sec REAL,
                start_lat REAL,
                start_lon REAL,
                end_lat REAL,
                end_lon REAL,
                max_altitude_m REAL,
                max_distance_m REAL,
                battery_start REAL,
                battery_end REAL,
                telemetry_data TEXT,
                events TEXT,
                status TEXT,
                FOREIGN KEY (mission_id) REFERENCES missions(id)
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_missions_type ON missions(mission_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_flight_logs_mission ON flight_logs(mission_id)")
        
        conn.commit()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
        return self._connection
    
    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    # Mission operations
    def create_mission(self, mission: Mission) -> int:
        """Create new mission."""
        conn = self._get_connection()
        
        cursor = conn.execute("""
            INSERT INTO missions (name, description, mission_type, waypoints, parameters,
                                 created_at, updated_at, status, flight_count, 
                                 total_flight_time_sec, tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            mission.name,
            mission.description,
            mission.mission_type,
            json.dumps(mission.waypoints),
            json.dumps(mission.parameters),
            mission.created_at,
            mission.updated_at,
            mission.status,
            mission.flight_count,
            mission.total_flight_time_sec,
            json.dumps(mission.tags),
            json.dumps(mission.metadata)
        ))
        
        conn.commit()
        return cursor.lastrowid
    
    def get_mission(self, mission_id: int) -> Optional[Mission]:
        """Get mission by ID."""
        conn = self._get_connection()
        
        row = conn.execute("SELECT * FROM missions WHERE id = ?", (mission_id,)).fetchone()
        
        if not row:
            return None
        
        return self._row_to_mission(row)
    
    def update_mission(self, mission: Mission) -> bool:
        """Update existing mission."""
        if not mission.id:
            return False
        
        conn = self._get_connection()
        
        mission.updated_at = time.time()
        
        conn.execute("""
            UPDATE missions SET
                name = ?, description = ?, mission_type = ?,
                waypoints = ?, parameters = ?, updated_at = ?,
                status = ?, tags = ?, metadata = ?
            WHERE id = ?
        """, (
            mission.name, mission.description, mission.mission_type,
            json.dumps(mission.waypoints), json.dumps(mission.parameters),
            mission.updated_at, mission.status, json.dumps(mission.tags),
            json.dumps(mission.metadata), mission.id
        ))
        
        conn.commit()
        return True
    
    def delete_mission(self, mission_id: int) -> bool:
        """Delete mission."""
        conn = self._get_connection()
        
        conn.execute("DELETE FROM missions WHERE id = ?", (mission_id,))
        conn.commit()
        
        return True
    
    def list_missions(self, mission_type: Optional[str] = None,
                     status: Optional[str] = None,
                     tag: Optional[str] = None) -> List[Mission]:
        """List missions with optional filters."""
        conn = self._get_connection()
        
        query = "SELECT * FROM missions WHERE 1=1"
        params = []
        
        if mission_type:
            query += " AND mission_type = ?"
            params.append(mission_type)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if tag:
            query += " AND tags LIKE ?"
            params.append(f'%{tag}%')
        
        query += " ORDER BY updated_at DESC"
        
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_mission(row) for row in rows]
    
    def _row_to_mission(self, row) -> Mission:
        """Convert database row to Mission."""
        return Mission(
            id=row['id'],
            name=row['name'],
            description=row['description'] or '',
            mission_type=row['mission_type'] or 'custom',
            waypoints=json.loads(row['waypoints'] or '[]'),
            parameters=json.loads(row['parameters'] or '{}'),
            created_at=row['created_at'] or 0,
            updated_at=row['updated_at'] or 0,
            status=row['status'] or 'draft',
            flight_count=row['flight_count'] or 0,
            total_flight_time_sec=row['total_flight_time_sec'] or 0,
            tags=json.loads(row['tags'] or '[]'),
            metadata=json.loads(row['metadata'] or '{}')
        )
    
    # Flight log operations
    def create_flight_log(self, log_entry: FlightLog) -> int:
        """Create new flight log entry."""
        conn = self._get_connection()
        
        cursor = conn.execute("""
            INSERT INTO flight_logs (mission_id, start_time, end_time, duration_sec,
                                   start_lat, start_lon, end_lat, end_lon,
                                   max_altitude_m, max_distance_m, battery_start,
                                   battery_end, telemetry_data, events, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log_entry.mission_id,
            log_entry.start_time, log_entry.end_time, log_entry.duration_sec,
            log_entry.start_lat, log_entry.start_lon, log_entry.end_lat, log_entry.end_lon,
            log_entry.max_altitude_m, log_entry.max_distance_m, log_entry.battery_start,
            log_entry.battery_end, log_entry.telemetry_data, log_entry.events,
            log_entry.status
        ))
        
        conn.commit()
        
        # Update mission flight count
        if log_entry.mission_id:
            conn.execute("""
                UPDATE missions SET 
                    flight_count = flight_count + 1,
                    total_flight_time_sec = total_flight_time_sec + ?
                WHERE id = ?
            """, (log_entry.duration_sec, log_entry.mission_id))
            conn.commit()
        
        return cursor.lastrowid
    
    def get_flight_log(self, log_id: int) -> Optional[FlightLog]:
        """Get flight log by ID."""
        conn = self._get_connection()
        
        row = conn.execute("SELECT * FROM flight_logs WHERE id = ?", (log_id,)).fetchone()
        
        if not row:
            return None
        
        return self._row_to_flight_log(row)
    
    def get_mission_flights(self, mission_id: int) -> List[FlightLog]:
        """Get all flight logs for a mission."""
        conn = self._get_connection()
        
        rows = conn.execute("""
            SELECT * FROM flight_logs WHERE mission_id = ? ORDER BY start_time DESC
        """, (mission_id,)).fetchall()
        
        return [self._row_to_flight_log(row) for row in rows]
    
    def _row_to_flight_log(self, row) -> FlightLog:
        """Convert database row to FlightLog."""
        return FlightLog(
            id=row['id'],
            mission_id=row['mission_id'],
            start_time=row['start_time'] or 0,
            end_time=row['end_time'] or 0,
            duration_sec=row['duration_sec'] or 0,
            start_lat=row['start_lat'] or 0,
            start_lon=row['start_lon'] or 0,
            end_lat=row['end_lat'] or 0,
            end_lon=row['end_lon'] or 0,
            max_altitude_m=row['max_altitude_m'] or 0,
            max_distance_m=row['max_distance_m'] or 0,
            battery_start=row['battery_start'] or 100,
            battery_end=row['battery_end'] or 0,
            telemetry_data=row['telemetry_data'] or '',
            events=row['events'] or '',
            status=row['status'] or 'unknown'
        )
    
    # Statistics
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        conn = self._get_connection()
        
        total_missions = conn.execute("SELECT COUNT(*) FROM missions").fetchone()[0]
        total_flights = conn.execute("SELECT COUNT(*) FROM flight_logs").fetchone()[0]
        total_flight_time = conn.execute("SELECT SUM(duration_sec) FROM flight_logs").fetchone()[0] or 0
        
        # Mission types breakdown
        types = conn.execute("""
            SELECT mission_type, COUNT(*) as count 
            FROM missions GROUP BY mission_type
        """).fetchall()
        
        return {
            'total_missions': total_missions,
            'total_flights': total_flights,
            'total_flight_time_sec': total_flight_time,
            'mission_types': {t['mission_type']: t['count'] for t in types}
        }
    
    # Export/Import
    def export_mission(self, mission_id: int) -> Optional[str]:
        """Export mission as JSON string."""
        mission = self.get_mission(mission_id)
        
        if not mission:
            return None
        
        return json.dumps(mission.to_dict(), indent=2)
    
    def import_mission(self, json_str: str) -> Optional[int]:
        """Import mission from JSON string."""
        try:
            data = json.loads(json_str)
            mission = Mission.from_dict(data)
            mission.id = None  # Create new ID
            return self.create_mission(mission)
        except (json.JSONDecodeError, KeyError) as e:
            log.error(f"Failed to import mission: {e}")
            return None


# Export
__all__ = ['MissionDatabase', 'Mission', 'FlightLog']