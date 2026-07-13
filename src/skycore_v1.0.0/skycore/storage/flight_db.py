"""
SkyCore Flight History Storage (SQLite)
Legal flight logging and replay
"""

import sqlite3
from datetime import datetime
from typing import List, Dict

class FlightDatabase:
    def __init__(self, db_path: str = "flights.db"):
        self.conn = sqlite3.connect(db_path)
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY,
                drone_id TEXT,
                start_time TEXT,
                end_time TEXT,
                max_alt REAL,
                distance_km REAL,
                battery_used REAL
            )
        """)
        self.conn.commit()

    def log_flight(self, drone_id: str, start: str, end: str, max_alt: float, 
                   distance: float, battery: float):
        self.conn.execute(
            "INSERT INTO flights VALUES (NULL, ?, ?, ?, ?, ?, ?)",
            (drone_id, start, end, max_alt, distance, battery)
        )
        self.conn.commit()
        print(f"📝 Flight logged for {drone_id}")

    def get_history(self, drone_id: str = None) -> List[Dict]:
        query = "SELECT * FROM flights"
        if drone_id:
            query += f" WHERE drone_id = '{drone_id}'"
        rows = self.conn.execute(query).fetchall()
        return [dict(zip([col[0] for col in self.conn.execute("PRAGMA table_info(flights)").fetchall()], row)) for row in rows]
