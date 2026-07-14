"""
SkyCore Flight History Storage (SQLite) — legal flight logging.

Vendored from skycore_v1.0.0/skycore/storage/flight_db.py with fixes:
  - get_history returned integer keys (PRAGMA col[0]=cid); use col[1]=name.
  - parametrised the drone_id filter (was an f-string / injectable).
  - check_same_thread=False so the async server can use one connection.
  - newest-first ordering.
  - durability/concurrency pragmas (WAL, busy_timeout, synchronous=NORMAL),
    an index on drone_id, a schema version stamp, and an explicit close().
"""
import sqlite3
from typing import Dict, List, Optional

SCHEMA_VERSION = 1


class FlightDatabase:
    def __init__(self, db_path: str = "flights.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        # Durability + concurrency: WAL lets a reader and a writer coexist; a busy
        # timeout avoids immediate SQLITE_BUSY under a second writer.
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()
        self._migrate()

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
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_flights_drone_id ON flights(drone_id)")
        self.conn.commit()

    def _migrate(self) -> None:
        """Stamp the schema version so future column changes can migrate an existing DB
        instead of silently no-op'ing against a stale CREATE TABLE IF NOT EXISTS."""
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        # (no migrations past v1 yet; add ordered steps here as the schema evolves)
        if version < SCHEMA_VERSION:
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
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

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
