"""Mission library — SQLite-backed save/load of WaypointMissions with tags.

Distinct from `skycore.storage.FlightDatabase`, which records flown
flights. The library stores **plans** — named, taggable, versioned
missions you can search and re-use.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from skycore.core.types import GeoPoint, MissionStep
from skycore.missions.waypoint import WaypointMission

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS mission_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    waypoints_json TEXT NOT NULL,
    tags TEXT,
    description TEXT,
    version INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mission_plans_name ON mission_plans(name);
"""


class MissionLibrary:
    def __init__(self, path: Path | str = "mission_library.db"):
        self.path = Path(path)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(str(self.path))
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "MissionLibrary":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def save(self, mission: WaypointMission, tags: Optional[list[str]] = None, description: str = "") -> int:
        wps = [
            {
                "lat": s.target.lat, "lon": s.target.lon, "alt": s.target.alt,
                "speed": s.speed_mps, "yaw": s.yaw_deg,
                "gimbal_pitch": s.gimbal_pitch_deg,
                "actions": list(s.actions),
                "hold_seconds": s.hold_seconds,
            }
            for s in mission.steps
        ]
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT INTO mission_plans (name, waypoints_json, tags, description, version, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 1, ?, ?)",
            (mission.name, json.dumps(wps), ",".join(tags or []), description, now, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def update(self, mission_id: int, mission: WaypointMission) -> None:
        wps = [
            {
                "lat": s.target.lat, "lon": s.target.lon, "alt": s.target.alt,
                "speed": s.speed_mps, "yaw": s.yaw_deg,
                "gimbal_pitch": s.gimbal_pitch_deg,
                "actions": list(s.actions),
                "hold_seconds": s.hold_seconds,
            }
            for s in mission.steps
        ]
        self._conn.execute(
            "UPDATE mission_plans SET waypoints_json = ?, version = version + 1, updated_at = ? WHERE id = ?",
            (json.dumps(wps), datetime.now(timezone.utc).isoformat(), mission_id),
        )
        self._conn.commit()

    def load(self, mission_id: int) -> Optional[WaypointMission]:
        row = self._conn.execute(
            "SELECT name, waypoints_json FROM mission_plans WHERE id = ?", (mission_id,)
        ).fetchone()
        if not row:
            return None
        m = WaypointMission(name=row[0])
        for wp in json.loads(row[1]):
            m.append(MissionStep(
                target=GeoPoint(wp["lat"], wp["lon"], wp.get("alt", 0)),
                speed_mps=wp.get("speed", 5.0),
                yaw_deg=wp.get("yaw"),
                gimbal_pitch_deg=wp.get("gimbal_pitch"),
                actions=wp.get("actions", []),
                hold_seconds=wp.get("hold_seconds", 0.0),
            ))
        return m

    def list(self, tag: Optional[str] = None, limit: int = 100) -> list[dict]:
        if tag:
            rows = self._conn.execute(
                "SELECT id, name, tags, description, version, created_at, updated_at FROM mission_plans "
                "WHERE tags LIKE ? ORDER BY updated_at DESC LIMIT ?",
                (f"%{tag}%", limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, name, tags, description, version, created_at, updated_at FROM mission_plans "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"id": r[0], "name": r[1], "tags": (r[2] or "").split(",") if r[2] else [],
             "description": r[3], "version": r[4], "created_at": r[5], "updated_at": r[6]}
            for r in rows
        ]

    def search(self, query: str, limit: int = 50) -> list[dict]:
        like = f"%{query}%"
        rows = self._conn.execute(
            "SELECT id, name, tags, description, version, created_at, updated_at FROM mission_plans "
            "WHERE name LIKE ? OR description LIKE ? OR tags LIKE ? ORDER BY updated_at DESC LIMIT ?",
            (like, like, like, limit),
        ).fetchall()
        return [
            {"id": r[0], "name": r[1], "tags": (r[2] or "").split(",") if r[2] else [],
             "description": r[3], "version": r[4], "created_at": r[5], "updated_at": r[6]}
            for r in rows
        ]

    def delete(self, mission_id: int) -> None:
        self._conn.execute("DELETE FROM mission_plans WHERE id = ?", (mission_id,))
        self._conn.commit()
