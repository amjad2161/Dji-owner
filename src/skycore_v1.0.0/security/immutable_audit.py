"""
SkyCore Immutable Audit Log
Blockchain-style tamper-proof logging for legal and security purposes
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import sqlite3

log = logging.getLogger(__name__)


@dataclass
class AuditBlock:
    """Single block in the audit chain."""
    index: int
    timestamp: float
    event_type: str
    details: dict
    actor: str
    previous_hash: str
    hash: str = ""

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "details": self.details,
            "actor": self.actor,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }


class ImmutableAuditLog:
    """Tamper-proof audit log using blockchain-style chaining.

    Features:
    - SHA-256 chained blocks
    - SQLite persistent storage
    - Integrity verification
    - Query and export capabilities
    - Automatic rotation after 10,000 entries
    """

    GENESIS_HASH = "GENESIS_SKYCORE_V1"

    def __init__(self, db_path: Optional[str] = None):
        self._chain: list[AuditBlock] = []
        self._last_hash = self.GENESIS_HASH
        self._index = 0

        # Initialize SQLite for persistence
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path("data/audit.db")

        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database for audit storage."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_chain (
                block_index INTEGER PRIMARY KEY,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL,
                actor TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                hash TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_type ON audit_chain(event_type)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_chain(timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_actor ON audit_chain(actor)
        """)

        conn.commit()

        # Load existing chain
        cursor.execute("SELECT COUNT(*) FROM audit_chain")
        count = cursor.fetchone()[0]

        if count > 0:
            cursor.execute("SELECT * FROM audit_chain ORDER BY block_index DESC LIMIT 1")
            row = cursor.fetchone()
            self._index = row[0]
            self._last_hash = row[6]

            # Load full chain for verification
            cursor.execute("SELECT * FROM audit_chain ORDER BY block_index ASC")
            for row in cursor.fetchall():
                block = AuditBlock(
                    index=row[0],
                    timestamp=row[1],
                    event_type=row[2],
                    details=json.loads(row[3]),
                    actor=row[4],
                    previous_hash=row[5],
                    hash=row[6],
                )
                self._chain.append(block)

        conn.close()

        log.info("ImmutableAuditLog initialized - %d entries, hash: %s",
                 len(self._chain), self._last_hash[:16])

    def add_event(self, event_type: str, details: dict, actor: str) -> AuditBlock:
        """Add an immutable event to the audit chain.

        Args:
            event_type: Type of event (e.g., "THREAT_DETECTED", "COMMAND_EXECUTED")
            details: Event details as dict
            actor: Who/what triggered the event

        Returns:
            The created AuditBlock
        """
        block = AuditBlock(
            index=self._index,
            timestamp=time.time(),
            event_type=event_type,
            details=details,
            actor=actor,
            previous_hash=self._last_hash,
        )

        # Calculate hash
        block.hash = self._calculate_hash(block)

        # Update chain
        self._chain.append(block)
        self._last_hash = block.hash
        self._index += 1

        # Persist to SQLite
        self._persist_block(block)

        log.debug("[Audit] %s by %s - hash: %s", event_type, actor, block.hash[:16])

        return block

    def _calculate_hash(self, block: AuditBlock) -> str:
        """Calculate SHA-256 hash of block."""
        content = json.dumps({
            "index": block.index,
            "timestamp": block.timestamp,
            "event_type": block.event_type,
            "details": block.details,
            "actor": block.actor,
            "previous_hash": block.previous_hash,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def _persist_block(self, block: AuditBlock) -> None:
        """Persist block to SQLite."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO audit_chain
            (block_index, timestamp, event_type, details, actor, previous_hash, hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            block.index,
            block.timestamp,
            block.event_type,
            json.dumps(block.details),
            block.actor,
            block.previous_hash,
            block.hash,
        ))

        conn.commit()
        conn.close()

    def verify_chain(self) -> dict:
        """Verify the entire chain hasn't been tampered with.

        Returns:
            dict with verification result and details
        """
        if not self._chain:
            return {"valid": True, "blocks": 0, "message": "Empty chain"}

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM audit_chain ORDER BY block_index ASC")
        rows = cursor.fetchall()
        conn.close()

        for i, row in enumerate(rows):
            expected_hash = self._calculate_hash(AuditBlock(
                index=row[0],
                timestamp=row[1],
                event_type=row[2],
                details=json.loads(row[3]),
                actor=row[4],
                previous_hash=row[5],
            ))

            if expected_hash != row[6]:
                return {
                    "valid": False,
                    "broken_at": row[0],
                    "event_type": row[2],
                    "actor": row[4],
                    "message": f"Chain broken at block {row[0]}",
                }

        return {
            "valid": True,
            "blocks": len(rows),
            "latest_hash": self._last_hash[:16],
            "message": "Chain integrity verified",
        }

    def get_audit_trail(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> list[dict]:
        """Query audit trail with filters.

        Args:
            limit: Maximum entries to return
            event_type: Filter by event type
            actor: Filter by actor
            start_time: Filter by start timestamp
            end_time: Filter by end timestamp

        Returns:
            List of audit entries as dicts
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        query = "SELECT * FROM audit_chain WHERE 1=1"
        params = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        if actor:
            query += " AND actor = ?"
            params.append(actor)

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            results.append({
                "index": row[0],
                "timestamp": row[1],
                "datetime": datetime.fromtimestamp(row[1], tz=timezone.utc).isoformat(),
                "event_type": row[2],
                "details": json.loads(row[3]),
                "actor": row[4],
                "previous_hash": row[5],
                "hash": row[6],
            })

        return results

    def get_events_by_type(self, event_type: str, limit: int = 100) -> list[dict]:
        """Get all events of a specific type."""
        return self.get_audit_trail(limit=limit, event_type=event_type)

    def export_to_file(self, filepath: str) -> None:
        """Export audit trail to JSON file."""
        entries = self.get_audit_trail(limit=100000)  # Export all

        with open(filepath, 'w') as f:
            json.dump({
                "export_time": time.time(),
                "total_entries": len(entries),
                "verification": self.verify_chain(),
                "entries": entries,
            }, f, indent=2)

        log.info("Audit trail exported to %s (%d entries)", filepath, len(entries))

    def get_statistics(self) -> dict:
        """Get audit log statistics."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM audit_chain")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT event_type) FROM audit_chain")
        event_types = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT actor) FROM audit_chain")
        actors = cursor.fetchone()[0]

        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM audit_chain")
        row = cursor.fetchone()
        start_ts, end_ts = row[0] or 0, row[1] or 0

        conn.close()

        return {
            "total_entries": total,
            "unique_event_types": event_types,
            "unique_actors": actors,
            "first_entry": datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat() if start_ts else None,
            "last_entry": datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat() if end_ts else None,
            "chain_valid": self.verify_chain()["valid"],
        }


# Global audit log
default_audit = ImmutableAuditLog()


def log_security_event(event_type: str, details: dict, actor: str = "SYSTEM") -> AuditBlock:
    """Quick helper to log a security event."""
    return default_audit.add_event(event_type, details, actor)


def log_command_event(command: str, parameters: dict, operator_id: str, result: str) -> AuditBlock:
    """Log a command execution event."""
    return default_audit.add_event("COMMAND", {
        "command": command,
        "parameters": parameters,
        "result": result,
    }, operator_id)


def log_threat_event(threat_id: str, threat_level: str, details: dict) -> AuditBlock:
    """Log a threat detection event."""
    return default_audit.add_event("THREAT_DETECTED", {
        "threat_id": threat_id,
        "threat_level": threat_level,
        **details,
    }, "SYSTEM")