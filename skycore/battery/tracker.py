"""Battery cycle and health tracker.

Logs each flight against a battery serial number, tracks total cycles, and
estimates remaining useful life. Health degrades as a function of cycles
and depth-of-discharge — we use a simple linear model:

    health = max(0, 100 - cycles * 0.05 - heavy_dod_count * 0.2)

Replaceable later with an ML model trained on telemetry.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS batteries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial TEXT UNIQUE NOT NULL,
    nominal_capacity_mah INTEGER,
    cell_count INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS battery_cycles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    battery_id INTEGER NOT NULL REFERENCES batteries(id) ON DELETE CASCADE,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    start_percent REAL,
    end_percent REAL,
    min_voltage REAL,
    flight_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_battery_cycles ON battery_cycles(battery_id);
"""


@dataclass
class BatteryRecord:
    serial: str
    nominal_capacity_mah: int = 0
    cell_count: int = 4
    notes: str = ""


@dataclass
class BatteryHealth:
    serial: str
    cycles: int
    heavy_discharge_count: int  # cycles ending below 10%
    estimated_health_pct: float
    avg_min_voltage: float = 0.0
    last_used: Optional[str] = None


class BatteryRegistry:
    def __init__(self, path: Path | str = "batteries.db"):
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

    def __enter__(self) -> "BatteryRegistry":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def register(self, record: BatteryRecord) -> int:
        """Register or upsert a battery. Returns its row id."""
        cur = self._conn.execute("SELECT id FROM batteries WHERE serial = ?", (record.serial,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur = self._conn.execute(
            "INSERT INTO batteries (serial, nominal_capacity_mah, cell_count, notes, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (record.serial, record.nominal_capacity_mah, record.cell_count, record.notes, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()
        return cur.lastrowid

    def start_cycle(self, serial: str, start_percent: float, flight_id: Optional[int] = None) -> int:
        battery_id = self.register(BatteryRecord(serial=serial))
        cur = self._conn.execute(
            "INSERT INTO battery_cycles (battery_id, started_at, start_percent, flight_id) VALUES (?, ?, ?, ?)",
            (battery_id, datetime.now(timezone.utc).isoformat(), start_percent, flight_id),
        )
        self._conn.commit()
        return cur.lastrowid

    def end_cycle(self, cycle_id: int, end_percent: float, min_voltage: float) -> None:
        self._conn.execute(
            "UPDATE battery_cycles SET ended_at = ?, end_percent = ?, min_voltage = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), end_percent, min_voltage, cycle_id),
        )
        self._conn.commit()

    def get_health(self, serial: str) -> Optional[BatteryHealth]:
        cur = self._conn.execute("SELECT id FROM batteries WHERE serial = ?", (serial,))
        row = cur.fetchone()
        if not row:
            return None
        battery_id = row[0]
        cycles_cur = self._conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN end_percent < 10 THEN 1 ELSE 0 END), AVG(min_voltage), MAX(ended_at) "
            "FROM battery_cycles WHERE battery_id = ? AND ended_at IS NOT NULL",
            (battery_id,),
        )
        cycles, heavy, avg_v, last = cycles_cur.fetchone()
        cycles = cycles or 0
        heavy = heavy or 0
        health = max(0.0, 100.0 - cycles * 0.05 - heavy * 0.2)
        return BatteryHealth(
            serial=serial,
            cycles=cycles,
            heavy_discharge_count=heavy,
            estimated_health_pct=health,
            avg_min_voltage=avg_v or 0.0,
            last_used=last,
        )

    def list_all(self) -> list[BatteryHealth]:
        cur = self._conn.execute("SELECT serial FROM batteries ORDER BY id")
        return [self.get_health(r[0]) for r in cur.fetchall() if r[0]]
