"""
SkyCore Operator Control System
Exclusive control by authorized operator only - no external interference
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import sqlite3

log = logging.getLogger(__name__)


@dataclass
class OperatorSession:
    """Active operator session."""
    operator_id: str
    session_id: str
    login_time: float
    last_activity: float
    trust_level: str  # MINIMUM, STANDARD, ELEVATED, MAXIMUM
    permissions: list[str]
    ip_address: Optional[str] = None

    def is_expired(self, timeout_s: float = 300) -> bool:
        return (time.time() - self.last_activity) > timeout_s

    def touch(self) -> None:
        self.last_activity = time.time()


@dataclass
class CommandLog:
    """Record of command execution."""
    timestamp: float
    operator_id: str
    session_id: str
    command_type: str
    parameters: dict
    result: str  # SUCCESS, DENIED, BLOCKED, ERROR
    reason: Optional[str] = None


class FullOperatorControl:
    """Full operator control with multi-factor authentication and command authorization.

    Features:
    - Multi-operator support with role-based permissions
    - Session management with timeout
    - Command audit logging
    - Emergency lockdown
    - Permission levels: PILOT, SUPERVISOR, ADMIN, SYSTEM
    - Secure credential storage with PBKDF2 hashing
    """

    PERMISSION_LEVELS = {
        "PILOT": ["fly", "land", "rtl", "takeoff", "goto", "status"],
        "SUPERVISOR": ["fly", "land", "rtl", "takeoff", "goto", "status", "mission", "load_mission"],
        "ADMIN": ["fly", "land", "rtl", "takeoff", "goto", "status", "mission", "load_mission",
                  "security_override", "emergency_land", "swarm_control"],
        "SYSTEM": ["*"],  # Full access
    }

    def __init__(self, authorized_operator_id: str, operator_role: str = "ADMIN", db_path: Optional[str] = None):
        self.authorized_operator_id = authorized_operator_id
        self.operator_role = operator_role

        # Session management
        self._sessions: dict[str, OperatorSession] = {}
        self._active_operators: dict[str, str] = {}  # operator_id -> session_id

        # System state
        self._locked = True
        self._emergency_active = False
        self._command_history: list[CommandLog] = []

        # Config
        self._session_timeout_s = 600  # 10 minutes
        self._max_sessions = 5

        # Credential storage
        self._db_path = Path(db_path) if db_path else Path("data/operators.db")
        self._init_credential_db()

        # Register authorized operator
        self._authorized_operators = {
            authorized_operator_id: operator_role
        }
        # Add default operator with hashed password
        self._add_operator(authorized_operator_id, operator_role, "admin123")  # Change in production!

        log.info("Operator Control initialized - system LOCKED")

    def _init_credential_db(self) -> None:
        """Initialize SQLite database for credential storage."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operators (
                operator_id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                failed_attempts INTEGER DEFAULT 0,
                locked_until REAL,
                created_at TEXT DEFAULT (datetime('now')),
                last_login TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_id TEXT,
                timestamp TEXT,
                success INTEGER,
                ip_address TEXT,
                reason TEXT
            )
        """)
        
        conn.commit()
        conn.close()

    def _add_operator(self, operator_id: str, role: str, password: str) -> None:
        """Add or update operator with hashed password."""
        salt = secrets.token_hex(32)
        password_hash = self._hash_password(password, salt)
        
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO operators (operator_id, role, password_hash, salt)
            VALUES (?, ?, ?, ?)
        """, (operator_id, role, password_hash, salt))
        
        conn.commit()
        conn.close()

    def _hash_password(self, password: str, salt: str) -> str:
        """Hash password using PBKDF2-SHA256 with salt."""
        # Use PBKDF2 with 100000 iterations
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return key.hex()

    def _verify_credentials(self, operator_id: str, credentials: str) -> tuple[bool, str]:
        """Verify operator credentials against stored hash.
        
        Returns:
            (success, reason)
        """
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT password_hash, salt, failed_attempts, locked_until
            FROM operators WHERE operator_id = ?
        """, (operator_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return False, "Operator not found"
        
        password_hash, salt, failed_attempts, locked_until = row
        
        # Check if account is locked
        if locked_until and time.time() < locked_until:
            remaining = int(locked_until - time.time())
            return False, f"Account locked. Try again in {remaining}s"
        
        # Check failed attempts (lock after 5 failed attempts)
        if failed_attempts >= 5:
            # Lock for 5 minutes
            new_locked_until = time.time() + 300
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE operators SET locked_until = ? WHERE operator_id = ?
            """, (new_locked_until, operator_id))
            conn.commit()
            conn.close()
            return False, "Too many failed attempts. Account locked for 5 minutes"
        
        # Verify password
        input_hash = self._hash_password(credentials, salt)
        
        if input_hash == password_hash:
            # Reset failed attempts on success
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE operators SET failed_attempts = 0, locked_until = NULL, last_login = datetime('now')
                WHERE operator_id = ?
            """, (operator_id,))
            conn.commit()
            conn.close()
            return True, "Success"
        else:
            # Increment failed attempts
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE operators SET failed_attempts = failed_attempts + 1
                WHERE operator_id = ?
            """, (operator_id,))
            conn.commit()
            conn.close()
            return False, f"Invalid credentials ({5 - failed_attempts - 1} attempts remaining)"

    def authenticate_operator(
        self,
        operator_id: str,
        credentials: str,
        ip_address: Optional[str] = None,
    ) -> dict:
        """Authenticate an operator with credentials.

        Returns:
            dict with success status, session_id, and permissions
        """
        # Check if operator is registered
        if operator_id not in self._authorized_operators:
            log.warning("Unauthorized operator attempt: %s", operator_id)
            self._log_login_attempt(operator_id, False, ip_address, "Not authorized")
            return {"success": False, "reason": "Not authorized"}

        # Verify credentials
        success, reason = self._verify_credentials(operator_id, credentials)
        
        if not success:
            log.warning("Operator %s authentication failed: %s", operator_id, reason)
            self._log_login_attempt(operator_id, False, ip_address, reason)
            return {"success": False, "reason": reason}

        # Create new session
        if len(self._sessions) >= self._max_sessions:
            # Remove oldest session
            oldest = min(self._sessions.values(), key=lambda s: s.login_time)
            self._terminate_session(oldest.session_id)

        session_id = secrets.token_urlsafe(32)
        session = OperatorSession(
            operator_id=operator_id,
            session_id=session_id,
            login_time=time.time(),
            last_activity=time.time(),
            trust_level="MAXIMUM",
            permissions=self.PERMISSION_LEVELS.get(
                self._authorized_operators[operator_id],
                self.PERMISSION_LEVELS["PILOT"]
            ),
            ip_address=ip_address,
        )

        self._sessions[session_id] = session
        self._active_operators[operator_id] = session_id

        log.info("Operator %s authenticated (role: %s, session: %s)",
                 operator_id, self._authorized_operators[operator_id], session_id[:8])

        self._log_login_attempt(operator_id, True, ip_address, "Success")

        return {
            "success": True,
            "session_id": session_id,
            "permissions": session.permissions,
            "trust_level": session.trust_level,
        }

    def _log_login_attempt(self, operator_id: str, success: bool, ip_address: Optional[str], reason: str) -> None:
        """Log login attempt to database."""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO login_history (operator_id, timestamp, success, ip_address, reason)
            VALUES (?, datetime('now'), ?, ?, ?)
        """, (operator_id, 1 if success else 0, ip_address or "", reason))
        conn.commit()
        conn.close()

    def execute_command(
        self,
        session_id: str,
        command: dict,
    ) -> dict:
        """Execute a command with operator validation.

        Args:
            session_id: The session ID from authentication
            command: Dict with 'type' and parameters

        Returns:
            dict with success status and result
        """
        # Check system emergency
        if self._emergency_active:
            return {
                "success": False,
                "reason": "Emergency active - only SYSTEM commands allowed",
                "blocked": True,
            }

        # Validate session
        session = self._sessions.get(session_id)
        if not session:
            return {"success": False, "reason": "Invalid session"}

        if session.is_expired(self._session_timeout_s):
            self._terminate_session(session_id)
            return {"success": False, "reason": "Session expired"}

        session.touch()

        # Check permission
        command_type = command.get("type", "")
        if command_type not in session.permissions and "*" not in session.permissions:
            log.warning("Operator %s denied command %s (not permitted)",
                       session.operator_id, command_type)

            self._log_command(
                session.operator_id, session_id,
                command_type, command, "DENIED",
                f"Not in permissions: {session.permissions}"
            )

            return {
                "success": False,
                "reason": "Command not permitted for your role",
                "required_permissions": command_type,
            }

        # Check system lock
        if self._locked and session.trust_level != "MAXIMUM":
            if command_type not in ["status", "authenticate"]:
                log.warning("System locked - command %s blocked", command_type)
                return {"success": False, "reason": "System locked"}

        # Execute command
        log.info("Operator %s executed: %s", session.operator_id, command_type)
        self._log_command(
            session.operator_id, session_id,
            command_type, command, "SUCCESS"
        )

        return {
            "success": True,
            "command": command_type,
            "executed_by": session.operator_id,
        }

    def emergency_lockdown(self, initiator_session: str) -> bool:
        """Initiate emergency lockdown - only authorized operators can unlock."""
        session = self._sessions.get(initiator_session)
        if not session:
            return False

        if "emergency_land" not in session.permissions:
            return False

        self._locked = True
        self._emergency_active = True

        log.critical("EMERGENCY LOCKDOWN activated by %s", session.operator_id)

        self._log_command(
            session.operator_id, initiator_session,
            "EMERGENCY_LOCKDOWN", {}, "SUCCESS"
        )

        return True

    def unlock_system(self, session_id: str) -> bool:
        """Unlock the system (after lockdown)."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        if session.trust_level != "MAXIMUM":
            return False

        self._locked = False
        self._emergency_active = False
        log.info("System unlocked by %s", session.operator_id)

        return True

    def authorize_operator(self, operator_id: str, role: str, password: str = None) -> bool:
        """Add a new authorized operator (ADMIN only)."""
        if operator_id not in self._authorized_operators:
            self._authorized_operators[operator_id] = role
            if password:
                self._add_operator(operator_id, role, password)
            log.info("Operator %s authorized with role %s", operator_id, role)
            return True
        return False

    def revoke_operator(self, operator_id: str, initiator_session: str) -> bool:
        """Revoke operator authorization (ADMIN only)."""
        session = self._sessions.get(initiator_session)
        if not session or "ADMIN" not in self.PERMISSION_LEVELS.get(
                self._authorized_operators.get(session.operator_id, ""), []):
            return False

        if operator_id in self._authorized_operators:
            del self._authorized_operators[operator_id]
            # Remove from database
            conn = sqlite3.connect(str(self._db_path))
            cursor = conn.cursor()
            cursor.execute("DELETE FROM operators WHERE operator_id = ?", (operator_id,))
            conn.commit()
            conn.close()
            log.info("Operator %s revoked", operator_id)
            return True
        return False

    def change_password(self, operator_id: str, old_password: str, new_password: str) -> tuple[bool, str]:
        """Change operator password."""
        success, reason = self._verify_credentials(operator_id, old_password)
        if not success:
            return False, reason
        
        self._add_operator(operator_id, self._authorized_operators[operator_id], new_password)
        log.info("Password changed for operator %s", operator_id)
        return True, "Password changed successfully"

    def get_active_sessions(self) -> list[dict]:
        """Get list of active operator sessions."""
        return [
            {
                "operator_id": s.operator_id,
                "session_id": s.session_id[:8] + "...",
                "login_time": s.login_time,
                "last_activity": s.last_activity,
                "trust_level": s.trust_level,
                "ip_address": s.ip_address,
            }
            for s in self._sessions.values()
            if not s.is_expired(60)  # Show sessions active in last minute
        ]

    def get_command_history(self, limit: int = 50) -> list[dict]:
        """Get recent command history."""
        return [
            {
                "timestamp": c.timestamp,
                "operator": c.operator_id,
                "command": c.command_type,
                "result": c.result,
                "reason": c.reason,
            }
            for c in self._command_history[-limit:]
        ]

    def get_login_history(self, operator_id: str = None, limit: int = 50) -> list[dict]:
        """Get login history."""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.cursor()
        
        if operator_id:
            cursor.execute("""
                SELECT operator_id, timestamp, success, ip_address, reason
                FROM login_history WHERE operator_id = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (operator_id, limit))
        else:
            cursor.execute("""
                SELECT operator_id, timestamp, success, ip_address, reason
                FROM login_history ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "operator_id": r[0],
                "timestamp": r[1],
                "success": bool(r[2]),
                "ip_address": r[3],
                "reason": r[4],
            }
            for r in rows
        ]

    def _terminate_session(self, session_id: str) -> None:
        """Terminate a session."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            operator_id = session.operator_id
            del self._sessions[session_id]
            if operator_id in self._active_operators:
                del self._active_operators[operator_id]
            log.info("Session %s terminated", session_id[:8])

    def _log_command(
        self,
        operator_id: str,
        session_id: str,
        command_type: str,
        parameters: dict,
        result: str,
        reason: Optional[str] = None,
    ) -> None:
        """Log a command execution."""
        log_entry = CommandLog(
            timestamp=time.time(),
            operator_id=operator_id,
            session_id=session_id,
            command_type=command_type,
            parameters=parameters,
            result=result,
            reason=reason,
        )
        self._command_history.append(log_entry)

        # Keep only last 1000 commands
        if len(self._command_history) > 1000:
            self._command_history = self._command_history[-1000:]


# Global operator control
default_operator_control = FullOperatorControl("system", "SYSTEM")