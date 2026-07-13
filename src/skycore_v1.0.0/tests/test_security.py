"""
Unit Tests for SkyCore Security Modules

Tests:
- operator_control.py (FullOperatorControl)
- immutable_audit.py (ImmutableAuditLog)
"""

import asyncio
import pytest
import time
from pathlib import Path
import tempfile
import os

import sys
sys.path.insert(0, "C:/Users/Mobar/Downloads/drone flycore/package/user_input_files")

from security.operator_control import FullOperatorControl, OperatorSession
from security.immutable_audit import ImmutableAuditLog, AuditBlock


class TestOperatorControl:
    """Tests for FullOperatorControl."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        try:
            os.unlink(path)
        except:
            pass
    
    @pytest.fixture
    def operator_control(self, temp_db):
        """Create fresh operator control instance."""
        oc = FullOperatorControl("test_admin", "ADMIN", db_path=temp_db)
        return oc
    
    def test_initialization(self, operator_control):
        """Test operator control initializes correctly."""
        assert operator_control._locked is True
        assert operator_control._emergency_active is False
        assert "test_admin" in operator_control._authorized_operators
    
    def test_successful_authentication(self, operator_control):
        """Test successful operator authentication."""
        result = operator_control.authenticate_operator("test_admin", "admin123")
        
        assert result["success"] is True
        assert "session_id" in result
        assert result["permissions"] == ["*"]  # SYSTEM role has all permissions
    
    def test_failed_authentication_wrong_password(self, operator_control):
        """Test authentication fails with wrong password."""
        result = operator_control.authenticate_operator("test_admin", "wrong_password")
        
        assert result["success"] is False
        assert "session_id" not in result
    
    def test_failed_authentication_unknown_operator(self, operator_control):
        """Test authentication fails for unknown operator."""
        result = operator_control.authenticate_operator("unknown_user", "password")
        
        assert result["success"] is False
        assert result["reason"] == "Not authorized"
    
    def test_command_execution_with_valid_session(self, operator_control):
        """Test command execution with valid session."""
        # First authenticate
        auth = operator_control.authenticate_operator("test_admin", "admin123")
        session_id = auth["session_id"]
        
        # Execute command
        result = operator_control.execute_command(session_id, {"type": "fly"})
        
        assert result["success"] is True
        assert result["command"] == "fly"
        assert result["executed_by"] == "test_admin"
    
    def test_command_execution_with_invalid_session(self, operator_control):
        """Test command fails with invalid session."""
        result = operator_control.execute_command("invalid_session_id", {"type": "fly"})
        
        assert result["success"] is False
        assert result["reason"] == "Invalid session"
    
    def test_command_with_insufficient_permissions(self, operator_control):
        """Test command fails with insufficient permissions."""
        # Add a pilot user
        operator_control._authorized_operators["pilot1"] = "PILOT"
        operator_control._add_operator("pilot1", "PILOT", "pilot_pass")
        
        # Authenticate as pilot
        auth = operator_control.authenticate_operator("pilot1", "pilot_pass")
        session_id = auth["session_id"]
        
        # Try admin command (should fail)
        result = operator_control.execute_command(session_id, {"type": "security_override"})
        
        assert result["success"] is False
        assert "not permitted" in result["reason"]
    
    def test_emergency_lockdown(self, operator_control):
        """Test emergency lockdown activation."""
        # Authenticate
        auth = operator_control.authenticate_operator("test_admin", "admin123")
        session_id = auth["session_id"]
        
        # Activate lockdown
        success = operator_control.emergency_lockdown(session_id)
        
        assert success is True
        assert operator_control._emergency_active is True
        assert operator_control._locked is True
    
    def test_unlock_system(self, operator_control):
        """Test system unlock after lockdown."""
        # Activate lockdown first
        auth = operator_control.authenticate_operator("test_admin", "admin123")
        session_id = auth["session_id"]
        operator_control.emergency_lockdown(session_id)
        
        # Unlock
        success = operator_control.unlock_system(session_id)
        
        assert success is True
        assert operator_control._locked is False
        assert operator_control._emergency_active is False
    
    def test_add_operator(self, operator_control):
        """Test adding new operator."""
        success = operator_control.authorize_operator("new_user", "PILOT", "new_pass")
        
        assert success is True
        assert "new_user" in operator_control._authorized_operators
        assert operator_control._authorized_operators["new_user"] == "PILOT"
    
    def test_revoke_operator(self, operator_control):
        """Test revoking operator."""
        # Add operator first
        operator_control.authorize_operator("revoke_me", "PILOT", "pass")
        
        # Authenticate as admin
        auth = operator_control.authenticate_operator("test_admin", "admin123")
        session_id = auth["session_id"]
        
        # Revoke
        success = operator_control.revoke_operator("revoke_me", session_id)
        
        assert success is True
        assert "revoke_me" not in operator_control._authorized_operators
    
    def test_session_timeout(self, operator_control):
        """Test session expiration."""
        # Authenticate
        auth = operator_control.authenticate_operator("test_admin", "admin123")
        session_id = auth["session_id"]
        
        # Manually expire session
        session = operator_control._sessions[session_id]
        session.last_activity = time.time() - 400  # 400 seconds ago (> 300 timeout)
        
        # Try command - should fail due to timeout
        result = operator_control.execute_command(session_id, {"type": "fly"})
        
        assert result["success"] is False
        assert result["reason"] == "Session expired"
    
    def test_max_sessions_limit(self, operator_control):
        """Test maximum sessions limit."""
        # Create 5 sessions (the max)
        sessions = []
        for i in range(5):
            # Add operators
            operator_control._authorized_operators[f"user{i}"] = "PILOT"
            operator_control._add_operator(f"user{i}", "PILOT", f"pass{i}")
            
            auth = operator_control.authenticate_operator(f"user{i}", f"pass{i}")
            sessions.append(auth["session_id"])
        
        # Now try to create 6th session - should evict oldest
        operator_control._authorized_operators["user5"] = "PILOT"
        operator_control._add_operator("user5", "PILOT", "pass5")
        auth = operator_control.authenticate_operator("user5", "pass5")
        
        # Should have 5 sessions total
        assert len(operator_control._sessions) == 5


class TestImmutableAuditLog:
    """Tests for ImmutableAuditLog."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        try:
            os.unlink(path)
        except:
            pass
    
    @pytest.fixture
    def audit_log(self, temp_db):
        """Create fresh audit log instance."""
        return ImmutableAuditLog(db_path=temp_db)
    
    def test_initialization(self, audit_log):
        """Test audit log initializes correctly."""
        assert audit_log._index == 0
        assert audit_log._last_hash == "GENESIS_SKYCORE_V1"
        assert len(audit_log._chain) == 0
    
    def test_add_event(self, audit_log):
        """Test adding audit event."""
        block = audit_log.add_event(
            event_type="TEST_EVENT",
            details={"key": "value"},
            actor="test_user"
        )
        
        assert block.index == 0
        assert block.event_type == "TEST_EVENT"
        assert block.actor == "test_user"
        assert block.hash != ""
        
        # Chain should have one block
        assert len(audit_log._chain) == 1
        assert audit_log._index == 1
    
    def test_verify_chain_empty(self, audit_log):
        """Test chain verification with no entries."""
        result = audit_log.verify_chain()
        
        assert result["valid"] is True
        assert result["blocks"] == 0
    
    def test_verify_chain_with_entries(self, audit_log):
        """Test chain verification with entries."""
        # Add some events
        for i in range(5):
            audit_log.add_event(f"EVENT_{i}", {"index": i}, "actor")
        
        result = audit_log.verify_chain()
        
        assert result["valid"] is True
        assert result["blocks"] == 5
    
    def test_chain_integrity_broken(self, audit_log):
        """Test detection of tampered chain."""
        # Add events
        audit_log.add_event("EVENT_1", {}, "actor")
        audit_log.add_event("EVENT_2", {}, "actor")
        
        # Tamper with database directly
        import sqlite3
        conn = sqlite3.connect(str(audit_log.db_path))
        cursor = conn.cursor()
        cursor.execute("UPDATE audit_chain SET details = 'TAMPERED' WHERE block_index = 1")
        conn.commit()
        conn.close()
        
        result = audit_log.verify_chain()
        
        assert result["valid"] is False
        assert "broken_at" in result
    
    def test_get_audit_trail(self, audit_log):
        """Test retrieving audit trail."""
        # Add events
        for i in range(10):
            audit_log.add_event(f"EVENT_{i}", {"data": i}, "actor")
        
        # Get all
        trail = audit_log.get_audit_trail(limit=100)
        assert len(trail) == 10
        
        # Get limited
        trail = audit_log.get_audit_trail(limit=5)
        assert len(trail) == 5
    
    def test_filter_by_event_type(self, audit_log):
        """Test filtering by event type."""
        audit_log.add_event("TYPE_A", {}, "actor")
        audit_log.add_event("TYPE_B", {}, "actor")
        audit_log.add_event("TYPE_A", {}, "actor")
        
        filtered = audit_log.get_audit_trail(limit=100, event_type="TYPE_A")
        
        assert len(filtered) == 2
        for entry in filtered:
            assert entry["event_type"] == "TYPE_A"
    
    def test_filter_by_actor(self, audit_log):
        """Test filtering by actor."""
        audit_log.add_event("EVENT", {}, "actor1")
        audit_log.add_event("EVENT", {}, "actor2")
        audit_log.add_event("EVENT", {}, "actor1")
        
        filtered = audit_log.get_audit_trail(limit=100, actor="actor1")
        
        assert len(filtered) == 2
        for entry in filtered:
            assert entry["actor"] == "actor1"
    
    def test_statistics(self, audit_log):
        """Test audit log statistics."""
        for i in range(5):
            audit_log.add_event(f"TYPE_{i % 3}", {}, f"actor{i % 2}")
        
        stats = audit_log.get_statistics()
        
        assert stats["total_entries"] == 5
        assert stats["unique_event_types"] == 3
        assert stats["unique_actors"] == 2
        assert stats["chain_valid"] is True
    
    def test_export_to_file(self, audit_log, temp_db):
        """Test exporting audit trail."""
        # Add events
        for i in range(3):
            audit_log.add_event(f"EVENT_{i}", {"data": i}, "actor")
        
        # Export
        export_path = temp_db.replace(".db", "_export.json")
        audit_log.export_to_file(export_path)
        
        # Verify file exists and contains data
        import json
        with open(export_path, 'r') as f:
            data = json.load(f)
        
        assert "entries" in data
        assert len(data["entries"]) == 3
        assert data["total_entries"] == 3
        
        # Cleanup
        os.unlink(export_path)


class TestPBKDF2PasswordHashing:
    """Tests for password hashing."""
    
    def test_password_hash_different_from_input(self):
        """Test that hash is different from password."""
        from security.operator_control import FullOperatorControl
        
        oc = FullOperatorControl("test", "ADMIN")
        hash_result = oc._hash_password("test_password", "test_salt")
        
        assert hash_result != "test_password"
        assert len(hash_result) == 64  # SHA-256 hex is 64 chars
    
    def test_same_password_different_hash_with_different_salt(self):
        """Test that same password with different salt produces different hash."""
        from security.operator_control import FullOperatorControl
        
        oc = FullOperatorControl("test", "ADMIN")
        
        hash1 = oc._hash_password("password", "salt1")
        hash2 = oc._hash_password("password", "salt2")
        
        assert hash1 != hash2
    
    def test_verification_succeeds_with_correct_password(self, temp_db):
        """Test credential verification with correct password."""
        from security.operator_control import FullOperatorControl
        
        oc = FullOperatorControl("test", "ADMIN", db_path=temp_db)
        success, reason = oc._verify_credentials("test", "admin123")
        
        assert success is True
        assert reason == "Success"
    
    def test_verification_fails_with_wrong_password(self, temp_db):
        """Test credential verification with wrong password."""
        from security.operator_control import FullOperatorControl
        
        oc = FullOperatorControl("test", "ADMIN", db_path=temp_db)
        success, reason = oc._verify_credentials("test", "wrong_password")
        
        assert success is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])