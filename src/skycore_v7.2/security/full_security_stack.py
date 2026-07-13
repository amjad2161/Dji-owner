"""
SkyCore Full Security Stack (Military Standard)
Combines Secure OTA + Runtime Integrity + Advanced Monitoring
"""

from security.secure_ota import SecureOTA
from security.runtime_integrity import RuntimeIntegrityMonitor
from security.drone_ids import DroneIDS
from security.immutable_audit import ImmutableAuditLog

class FullSecurityStack:
    def __init__(self):
        self.ota = SecureOTA()
        self.integrity = RuntimeIntegrityMonitor()
        self.ids = DroneIDS()
        self.audit = ImmutableAuditLog()

    def full_check(self, drone_id: str, current_state: dict) -> Dict:
        """Run full security check on a drone"""
        results = {
            "drone_id": drone_id,
            "timestamp": "now",
            "checks": {}
        }

        # 1. Integrity check
        if "system_hash" in current_state:
            integrity_ok = self.integrity.check_integrity(drone_id, current_state["system_hash"])
            results["checks"]["integrity"] = "OK" if integrity_ok else "TAMPERED"

        # 2. Anomaly detection
        anomalies = self.ids.detect_anomaly(drone_id, current_state)
        results["checks"]["anomalies"] = len(anomalies)

        # 3. Log everything
        self.audit.add_event("SECURITY_CHECK", results, "SYSTEM")

        return results
