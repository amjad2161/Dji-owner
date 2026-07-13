"""SQLite-backed flight history storage.

Stores telemetry snapshots, mission plans, weather at time of flight,
and operator notes. Enables post-flight analytics and trend tracking.

Schema:
    flights: id, drone_name, drone_model, operator, started_at, ended_at,
            home_lat, home_lon, max_altitude_m, max_distance_m, battery_drain_pct,
            weather_snapshot_json, mission_plan_json, notes, manifest_path
    telemetry_snapshots: id, flight_id, timestamp, lat, lon, alt, battery_pct
    waypoints_executed: id, flight_id, index, lat, lon, alt, yaw, action, ts
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from skycore.core.types import GeoPoint

log = logging.getLogger(__name__)


@dataclass
class FlightRecord:
    """One complete flight record."""
    id: int
    drone_name: str
    drone_model: str
    operator: str
    started_at: datetime
    ended_at: Optional[datetime]
    home: Optional[GeoPoint]
    max_altitude_m: float
    max_distance_m: float
    battery_drain_pct: float
    weather: Optional[dict] = None
    mission: Optional[dict] = None
    notes: str = ""
    manifest_path: Optional[str] = None

    @property
    def duration_min(self) -> Optional[float]:
        if self.ended_at and self.started_at:
            return (self.ended_at - self.started_at).total_seconds() / 60
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "drone": self.drone_name,
            "model": self.drone_model,
            "operator": self.operator,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_min": self.duration_min,
            "home": {"lat": self.home.lat, "lon": self.home.lon} if self.home else None,
            "max_altitude_m": self.max_altitude_m,
            "max_distance_m": self.max_distance_m,
            "battery_drain_pct": self.battery_drain_pct,
            "weather": self.weather,
            "mission": self.mission,
            "notes": self.notes,
            "manifest_path": self.manifest_path,
        }


class FlightDatabase:
    """SQLite-backed flight history."""

    def __init__(self, path: str = "skycore.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS flights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    drone_name TEXT NOT NULL DEFAULT '',
                    drone_model TEXT NOT NULL DEFAULT '',
                    operator TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    home_lat REAL,
                    home_lon REAL,
                    max_altitude_m REAL DEFAULT 0,
                    max_distance_m REAL DEFAULT 0,
                    battery_drain_pct REAL DEFAULT 0,
                    weather_json TEXT,
                    mission_json TEXT,
                    notes TEXT DEFAULT '',
                    manifest_path TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS telemetry_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flight_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    lat REAL,
                    lon REAL,
                    alt REAL,
                    battery_pct REAL,
                    FOREIGN KEY (flight_id) REFERENCES flights(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS waypoints_executed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flight_id INTEGER NOT NULL,
                    wp_index INTEGER NOT NULL,
                    lat REAL,
                    lon REAL,
                    alt REAL,
                    yaw_deg REAL,
                    action TEXT,
                    executed_at TEXT,
                    FOREIGN KEY (flight_id) REFERENCES flights(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_telemetry_flight ON telemetry_snapshots(flight_id);
                CREATE INDEX IF NOT EXISTS idx_waypoints_flight ON waypoints_executed(flight_id);
                CREATE INDEX IF NOT EXISTS idx_flights_started ON flights(started_at);
            """)
            conn.commit()

    def start_flight(
        self,
        drone_name: str,
        drone_model: str,
        operator: str = "",
        home: Optional[GeoPoint] = None,
    ) -> int:
        """Start a new flight session. Returns flight_id."""
        with self._conn() as conn:
            now = datetime.now(timezone.utc).isoformat()
            cursor = conn.execute(
                """INSERT INTO flights (drone_name, drone_model, operator, started_at, home_lat, home_lon)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    drone_name,
                    drone_model,
                    operator,
                    now,
                    home.lat if home else None,
                    home.lon if home else None,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def end_flight(
        self,
        flight_id: int,
        max_altitude_m: float = 0,
        max_distance_m: float = 0,
        battery_drain_pct: float = 0,
        weather: Optional[dict] = None,
        mission: Optional[dict] = None,
        notes: str = "",
    ) -> None:
        """Finalize a flight session."""
        with self._conn() as conn:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """UPDATE flights SET
                    ended_at = ?,
                    max_altitude_m = ?,
                    max_distance_m = ?,
                    battery_drain_pct = ?,
                    weather_json = ?,
                    mission_json = ?,
                    notes = ?
                   WHERE id = ?""",
                (
                    now,
                    max_altitude_m,
                    max_distance_m,
                    battery_drain_pct,
                    json.dumps(weather) if weather else None,
                    json.dumps(mission) if mission else None,
                    notes,
                    flight_id,
                ),
            )
            conn.commit()

    def log_telemetry(
        self,
        flight_id: int,
        timestamp: datetime,
        lat: float,
        lon: float,
        alt: float,
        battery_pct: float,
    ) -> None:
        """Log a telemetry point (call in batch for performance)."""
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO telemetry_snapshots (flight_id, timestamp, lat, lon, alt, battery_pct)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (flight_id, timestamp.isoformat(), lat, lon, alt, battery_pct),
            )

    def log_telemetry_batch(self, flight_id: int, points: list[dict]) -> None:
        """Batch insert telemetry points."""
        with self._conn() as conn:
            conn.executemany(
                """INSERT INTO telemetry_snapshots (flight_id, timestamp, lat, lon, alt, battery_pct)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (flight_id, p["timestamp"], p["lat"], p["lon"], p["alt"], p["battery"])
                    for p in points
                ],
            )
            conn.commit()

    def log_waypoint(
        self,
        flight_id: int,
        wp_index: int,
        lat: float,
        lon: float,
        alt: float,
        yaw_deg: float,
        action: str = "",
    ) -> None:
        """Log waypoint execution."""
        with self._conn() as conn:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """INSERT INTO waypoints_executed
                   (flight_id, wp_index, lat, lon, alt, yaw_deg, action, executed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (flight_id, wp_index, lat, lon, alt, yaw_deg, action, now),
            )
            conn.commit()

    def get_flight(self, flight_id: int) -> Optional[FlightRecord]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM flights WHERE id = ?", (flight_id,)).fetchone()
        if not row:
            return None
        return self._row_to_flight(row)

    def list_flights(self, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, drone_name, drone_model, operator, started_at, ended_at,
                          home_lat, home_lon, max_altitude_m, max_distance_m, battery_drain_pct,
                          notes, manifest_path
                   FROM flights ORDER BY started_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_telemetry(self, flight_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT timestamp, lat, lon, alt, battery_pct
                   FROM telemetry_snapshots WHERE flight_id = ? ORDER BY timestamp""",
                (flight_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_waypoints(self, flight_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT wp_index, lat, lon, alt, yaw_deg, action, executed_at
                   FROM waypoints_executed WHERE flight_id = ? ORDER BY wp_index""",
                (flight_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_flight(self, flight_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM flights WHERE id = ?", (flight_id,))
            conn.commit()

    def _row_to_flight(self, row: sqlite3.Row) -> FlightRecord:
        home = None
        if row["home_lat"] is not None and row["home_lon"] is not None:
            home = GeoPoint(row["home_lat"], row["home_lon"])

        weather = None
        if row["weather_json"]:
            try:
                weather = json.loads(row["weather_json"])
            except json.JSONDecodeError:
                pass

        mission = None
        if row["mission_json"]:
            try:
                mission = json.loads(row["mission_json"])
            except json.JSONDecodeError:
                pass

        return FlightRecord(
            id=row["id"],
            drone_name=row["drone_name"],
            drone_model=row["drone_model"],
            operator=row["operator"],
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            home=home,
            max_altitude_m=row["max_altitude_m"],
            max_distance_m=row["max_distance_m"],
            battery_drain_pct=row["battery_drain_pct"],
            weather=weather,
            mission=mission,
            notes=row["notes"] or "",
            manifest_path=row["manifest_path"],
        )

    def stats(self) -> dict:
        """Aggregate statistics across all flights."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
            with_flight = conn.execute(
                "SELECT COUNT(*) FROM flights WHERE ended_at IS NOT NULL"
            ).fetchone()[0]
            avg_alt = conn.execute(
                "SELECT AVG(max_altitude_m) FROM flights WHERE max_altitude_m > 0"
            ).fetchone()[0] or 0
            avg_dist = conn.execute(
                "SELECT AVG(max_distance_m) FROM flights WHERE max_distance_m > 0"
            ).fetchone()[0] or 0
            total_telemetry = conn.execute(
                "SELECT COUNT(*) FROM telemetry_snapshots"
            ).fetchone()[0]
        return {
            "total_flights": total,
            "completed_flights": with_flight,
            "avg_max_altitude_m": round(avg_alt, 1),
            "avg_max_distance_m": round(avg_dist, 1),
            "total_telemetry_points": total_telemetry,
        }