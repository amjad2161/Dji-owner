"""
SkyCore Flight History Storage (SQLite) — legal flight logging.

Vendored from skycore_v1.0.0/skycore/storage/flight_db.py with fixes:
  - get_history returned integer keys (PRAGMA col[0]=cid); use col[1]=name.
  - parametrised the drone_id filter (was an f-string / injectable).
  - check_same_thread=False so the async server can use one connection.
  - newest-first ordering.
"""
import sqlite3
from typing import Dict, List, Optional


class FlightDatabase:
    def __init__(self, db_path: str = "flights.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY,
                drone_id TEXT,
                start_time TEXT,
                end_time TEXT,
                max_alt REAL,
                distance_km REAL,
                battery_used REAL
            )
            """
        )
        self.conn.commit()

    def log_flight(self, drone_id: str, start: str, end: str, max_alt: float,
                   distance: float, battery: float) -> None:
        self.conn.execute(
            "INSERT INTO flights VALUES (NULL, ?, ?, ?, ?, ?, ?)",
            (drone_id, start, end, max_alt, distance, battery),
        )
        self.conn.commit()

    def get_history(self, drone_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        cols = [c[1] for c in self.conn.execute("PRAGMA table_info(flights)").fetchall()]
        if drone_id:
            rows = self.conn.execute(
                "SELECT * FROM flights WHERE drone_id = ? ORDER BY id DESC LIMIT ?",
                (drone_id, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM flights ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(zip(cols, row)) for row in rows]
