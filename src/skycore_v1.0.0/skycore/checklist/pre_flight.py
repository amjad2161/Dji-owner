"""
SkyCore Pre-Flight Checklist
Aggregated safety checklist (weather + geofence + battery + airspace)
"""

from typing import List

class PreFlightChecklist:
    def run_full_check(self, drone_id: str, lat: float, lon: float, weather_safe: bool, 
                       battery: float, in_geofence: bool, airspace_clear: bool) -> List[str]:
        issues = []
        
        if not weather_safe:
            issues.append("❌ Weather not safe for flight")
        if battery < 30:
            issues.append("❌ Battery too low (<30%)")
        if not in_geofence:
            issues.append("❌ Outside geofence")
        if not airspace_clear:
            issues.append("❌ Airspace conflict detected (ADS-B)")
        
        if not issues:
            issues.append("✅ All checks passed - Ready for takeoff")
        
        return issues
