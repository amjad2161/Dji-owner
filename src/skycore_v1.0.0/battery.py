"""Battery health tracking and lifecycle management.

Tracks cycles, capacity degradation, and estimates health based on
voltage sag under load. Works offline — no DJI account required.

Schema:
    Serial number, firmware version, manufacturing date
    Cycle count (full charge = 1 cycle)
    Heavy discharge count (below 20% DOD threshold)
    Charge count
    Health estimate based on internal resistance + sag

Usage:
    registry = BatteryRegistry("batteries.db")
    reg.log_charge_cycle("BATT123", health_pct=95)
    reg.log_flight("BATT123", drain_pct=45, voltage_sag=0.8)
    h = reg.get_health("BATT123")
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class BatteryCycle:
    """One charge cycle."""
    serial: str
    started_at: datetime
    ended_at: Optional[datetime]
    start_pct: float
    end_pct: float
    charge_duration_min: Optional[float]
    health_pct: Optional[float]
    voltage_sag: Optional[float]  # V drop under load at end of charge


@dataclass
class BatteryHistory:
    """Aggregated battery history."""
    serial: str
    firmware: str = ""
    manufactured_date: Optional[datetime] = None
    cycles: int = 0
    charge_count: int = 0
    heavy_discharge_count: int = 0
    avg_min_voltage: float = 0.0
    estimated_health_pct: float = 100.0
    last_used: Optional[datetime] = None
    last_charge_at: Optional[datetime] = None

    @property
    def age_days(self) -> Optional[int]:
        if self.manufactured_date:
            return (datetime.now(timezone.utc) - self.manufactured_date).days
        return None

    def to_dict(self) -> dict:
        return {
            "serial": self.serial,
            "firmware": self.firmware,
            "manufactured_date": self.manufactured_date.isoformat() if self.manufactured_date else None,
            "cycles": self.cycles,
            "charge_count": self.charge_count,
            "heavy_discharge_count": self.heavy_discharge_count,
            "avg_min_voltage": self.avg_min_voltage,
            "estimated_health_pct": self.estimated_health_pct,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "last_charge_at": self.last_charge_at.isoformat() if self.last_charge_at else None,
            "age_days": self.age_days,
        }


class BatteryRegistry:
    """SQLite-backed battery health registry."""

    def __init__(self, path: str = "batteries.db"):
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
                CREATE TABLE IF NOT EXISTS batteries (
                    serial TEXT PRIMARY KEY,
                    firmware TEXT DEFAULT '',
                    manufactured_date TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    cycles INTEGER DEFAULT 0,
                    charge_count INTEGER DEFAULT 0,
                    heavy_discharge_count INTEGER DEFAULT 0,
                    total_voltage_sag REAL DEFAULT 0.0,
                    voltage_sag_count INTEGER DEFAULT 0,
                    last_used TEXT,
                    last_charge_at TEXT
                );

                CREATE TABLE IF NOT EXISTS cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    serial TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    start_pct REAL,
                    end_pct REAL,
                    charge_duration_min REAL,
                    health_pct REAL,
                    voltage_sag REAL,
                    FOREIGN KEY (serial) REFERENCES batteries(serial)
                );

                CREATE INDEX IF NOT EXISTS idx_cycles_serial ON cycles(serial);
                CREATE INDEX IF NOT EXISTS idx_cycles_started ON cycles(started_at);
            """)
            conn.commit()

    def register(self, serial: str, firmware: str = "", manufactured_date: Optional[str] = None) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO batteries (serial, firmware, manufactured_date)
                   VALUES (?, ?, ?)""",
                (serial, firmware, manufactured_date),
            )
            conn.commit()

    def log_charge_start(self, serial: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO cycles (serial, started_at, start_pct)
                   VALUES (?, datetime('now'), 100.0)""",
                (serial,),
            )
            conn.commit()

    def log_charge_end(
        self,
        serial: str,
        end_pct: float,
        health_pct: Optional[float] = None,
        voltage_sag: Optional[float] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        with self._conn() as conn:
            # Find the latest open cycle
            row = conn.execute(
                """SELECT id, start_pct FROM cycles
                   WHERE serial = ? AND ended_at IS NULL
                   ORDER BY started_at DESC LIMIT 1""",
                (serial,),
            ).fetchone()

            if row:
                started = datetime.fromisoformat(conn.execute(
                    "SELECT started_at FROM cycles WHERE id = ?", (row["id"],)
                ).fetchone()["started_at"])

                charge_min = (now - started).total_seconds() / 60

                conn.execute(
                    """UPDATE cycles SET
                        ended_at = ?,
                        end_pct = ?,
                        charge_duration_min = ?,
                        health_pct = ?,
                        voltage_sag = ?
                       WHERE id = ?""",
                    (now.isoformat(), end_pct, charge_min, health_pct, voltage_sag, row["id"]),
                )

            # Update battery stats
            conn.execute(
                """UPDATE batteries SET
                    last_charge_at = ?,
                    charge_count = charge_count + 1
                   WHERE serial = ?""",
                (now.isoformat(), serial),
            )

            # If it was a deep discharge (ended very low), count it
            if end_pct < 20:
                conn.execute(
                    """UPDATE batteries SET heavy_discharge_count = heavy_discharge_count + 1
                       WHERE serial = ?""",
                    (serial,),
                )

            # If health and sag provided, track them
            if health_pct is not None and voltage_sag is not None:
                conn.execute(
                    """UPDATE batteries SET
                        total_voltage_sag = total_voltage_sag + ?,
                        voltage_sag_count = voltage_sag_count + 1
                       WHERE serial = ?""",
                    (voltage_sag, serial),
                )

            conn.commit()

    def log_flight(self, serial: str, drain_pct: float, voltage_sag: float = 0.0) -> None:
        """Log that a battery was used in a flight (completes a cycle)."""
        now = datetime.now(timezone.utc)
        with self._conn() as conn:
            # Complete any open charge cycle
            conn.execute(
                """UPDATE cycles SET ended_at = ?, end_pct = ?, voltage_sag = ?
                   WHERE serial = ? AND ended_at IS NULL""",
                (now.isoformat(), 100.0 - drain_pct, voltage_sag, serial),
            )

            # Update battery
            conn.execute(
                """UPDATE batteries SET
                    last_used = ?,
                    cycles = cycles + 1
                   WHERE serial = ?""",
                (now.isoformat(), serial),
            )
            conn.commit()

    def get_health(self, serial: str) -> Optional[BatteryHistory]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM batteries WHERE serial = ?", (serial,)
            ).fetchone()
            if not row:
                return None

            avg_sag = row["total_voltage_sag"] / row["voltage_sag_count"] if row["voltage_sag_count"] > 0 else 0.0

            # Estimate health: degrade by 0.5% per cycle + 2% per heavy discharge
            # + extra if voltage sag is high (>1V indicates degradation)
            cycle_penalty = row["cycles"] * 0.5
            dod_penalty = row["heavy_discharge_count"] * 2.0
            sag_penalty = min(20.0, avg_sag * 10)  # 0.1V sag = 1% penalty, max 20%

            health = max(0.0, 100.0 - cycle_penalty - dod_penalty - sag_penalty)

            return BatteryHistory(
                serial=row["serial"],
                firmware=row["firmware"],
                manufactured_date=datetime.fromisoformat(row["manufactured_date"]) if row["manufactured_date"] else None,
                cycles=row["cycles"],
                charge_count=row["charge_count"],
                heavy_discharge_count=row["heavy_discharge_count"],
                avg_min_voltage=avg_sag,
                estimated_health_pct=health,
                last_used=datetime.fromisoformat(row["last_used"]) if row["last_used"] else None,
                last_charge_at=datetime.fromisoformat(row["last_charge_at"]) if row["last_charge_at"] else None,
            )

    def list_all(self) -> list[Optional[BatteryHistory]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT serial FROM batteries ORDER BY last_used DESC").fetchall()
        return [self.get_health(r["serial"]) for r in rows]

    def get_cycle_history(self, serial: str, limit: int = 50) -> list[BatteryCycle]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM cycles WHERE serial = ? ORDER BY started_at DESC LIMIT ?""",
                (serial, limit),
            ).fetchall()
        return [
            BatteryCycle(
                serial=r["serial"],
                started_at=datetime.fromisoformat(r["started_at"]),
                ended_at=datetime.fromisoformat(r["ended_at"]) if r["ended_at"] else None,
                start_pct=r["start_pct"] or 0,
                end_pct=r["end_pct"] or 0,
                charge_duration_min=r["charge_duration_min"],
                health_pct=r["health_pct"],
                voltage_sag=r["voltage_sag"],
            )
            for r in rows
        ]

    def get_charge_time_avg(self, serial: str) -> Optional[float]:
        """Average charge time in minutes over last 10 cycles."""
        with self._conn() as conn:
            row = conn.execute(
                """SELECT AVG(charge_duration_min) as avg_min
                   FROM (SELECT charge_duration_min FROM cycles
                         WHERE serial = ? AND charge_duration_min IS NOT NULL
                         ORDER BY started_at DESC LIMIT 10)""",
                (serial,),
            ).fetchone()
        return row["avg_min"] if row and row["avg_min"] else None

    def needs_replacement(self, serial: str, threshold_pct: float = 70.0) -> tuple[bool, str]:
        """Check if battery should be replaced."""
        h = self.get_health(serial)
        if h is None:
            return False, "unknown"
        if h.estimated_health_pct < threshold_pct:
            return True, f"health {h.estimated_health_pct:.0f}% below threshold"
        if h.heavy_discharge_count > 50:
            return True, f"heavy discharge count {h.heavy_discharge_count} > 50"
        if h.cycles > 300:
            return True, f"cycle count {h.cycles} > 300"
        return False, f"healthy ({h.estimated_health_pct:.0f}%)"