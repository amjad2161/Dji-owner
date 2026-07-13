"""
SkyCore Professional Security Reporting
Automated threat reports for command & legal use
"""

from datetime import datetime
from typing import List
from cuas.threat_detector import Threat

class SecurityReporter:
    def generate_threat_report(self, threats: List[Threat], period: str = "24h") -> str:
        report = f"""
=== SECURITY THREAT REPORT ({period}) ===
Generated: {datetime.now()}
Unit: National Security Command

Total Threats Detected: {len(threats)}
High/Critical: {len([t for t in threats if t.threat_level in ['HIGH', 'CRITICAL']])}

"""
        for t in threats:
            report += f"- {t.timestamp} | {t.classification} | Level: {t.threat_level} | Action: {t.recommended_action}\n"
        
        report += "\n=== END OF REPORT ===\n"
        return report

    def export_for_legal(self, threats: List[Threat]) -> str:
        """Immutable style report for legal purposes"""
        return f"LEGAL AUDIT LOG - {len(threats)} incidents recorded at {datetime.now()}"
