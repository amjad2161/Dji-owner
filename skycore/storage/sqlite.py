"""SQLite-backed flight history.

No external dependencies — sqlite3 is in the standard library. Tables:

- flights: one row per flight
- telemetry: time-series points keyed by flight_id
- missions: saved mission definitions
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS flights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drone_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    home_lat REAL,
    home_lon REAL,
    summary_json TEXT
);

CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id INTEGER NOT NULL REFERENCES flights(id) ON DELETE CASCADE,
    ts TEXT NOT NULL,
    lat REAL,
    lon REAL,
    alt REAL,
    yaw REAL,
    battery_percent REAL,
    raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_telemetry_flight ON telemetry(flight_id);

CREATE TABLE IF NOT EXISTS missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    waypoints_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class FlightDatabase:
    def __init__(self, path: Path | str = "skycore.db"):
        self.path = Path(path)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "FlightDatabase":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def start_flight(self, drone_name: str, home_lat: float, home_lon: float) -> int:
        cur = self._conn.execute(
            "INSERT INTO flights (drone_name, started_at, home_lat, home_lon) VALUES (?, ?, ?, ?)",
            (drone_name, datetime.now(timezone.utc).isoformat(), home_lat, home_lon),
        )
        self._conn.commit()
        return cur.lastrowid

    def end_flight(self, flight_id: int, summary: dict) -> None:
        self._conn.execute(
            "UPDATE flights SET ended_at = ?, summary_json = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), json.dumps(summary), flight_id),
        )
        self._conn.commit()

    def record_telemetry(self, flight_id: int, telemetry_dict: dict) -> None:
        pos = telemetry_dict.get("position", {})
        self._conn.execute(
            "INSERT INTO telemetry (flight_id, ts, lat, lon, alt, yaw, battery_percent, raw_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                flight_id,
                telemetry_dict.get("timestamp"),
                pos.get("lat"),
                pos.get("lon"),
                pos.get("alt"),
                telemetry_dict.get("yaw"),
                (telemetry_dict.get("battery") or {}).get("percent"),
                json.dumps(telemetry_dict),
            ),
        )

    def commit(self) -> None:
        self._conn.commit()

    def list_flights(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, drone_name, started_at, ended_at, home_lat, home_lon, summary_json "
            "FROM flights ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "drone": r[1],
                "started_at": r[2],
                "ended_at": r[3],
                "home": {"lat": r[4], "lon": r[5]},
                "summary": json.loads(r[6]) if r[6] else None,
            }
            for r in rows
        ]

    def get_telemetry(self, flight_id: int, limit: int = 10_000) -> list[dict]:
        rows = self._conn.execute(
            "SELECT ts, lat, lon, alt, yaw, battery_percent FROM telemetry "
            "WHERE flight_id = ? ORDER BY id LIMIT ?",
            (flight_id, limit),
        ).fetchall()
        return [
            {"ts": r[0], "lat": r[1], "lon": r[2], "alt": r[3], "yaw": r[4], "battery": r[5]}
            for r in rows
        ]

    def save_mission(self, name: str, waypoints: list[dict]) -> int:
        cur = self._conn.execute(
            "INSERT INTO missions (name, waypoints_json, created_at) VALUES (?, ?, ?)",
            (name, json.dumps(waypoints), datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()
        return cur.lastrowid
