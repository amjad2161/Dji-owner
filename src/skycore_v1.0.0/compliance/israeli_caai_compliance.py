"""
SkyCore Israeli CFF/משרד התחבורה Compliance Module
==========================================

Israeli Civil Aviation Authority (CAAI / רשות התעופה האזרחית) 
drone regulations and compliance

Key areas:
- Registration requirements
- No-fly zones (Ben Gurion, military, Gaza border)
- Frequency allocation (matching CE for drones)
- Remote ID requirements
- Operator licensing
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IsraelZone(Enum):
    """Israeli airspace zones"""
    OPEN = "A"           # Green - open
    CONTROLLED = "B"     # Yellow - controlled
    RESTRICTED = "C"     # Red - no fly
    DANGEROUS = "D"      # Orange - dangerous


@dataclass
class IsraelNoFlyZone:
    """Israeli no-fly zone"""
    name: str
    zone_type: IsraelZone
    center: Tuple[float, float]  # lat, lon
    radius_km: float
    max_altitude_m: float = 999999
    description: str = ""
    
    def contains_point(self, lat: float, lon: float) -> bool:
        """Check if point is inside zone"""
        # Haversine distance
        R = 6371  # Earth radius in km
        
        lat1 = math.radians(self.center[0])
        lat2 = math.radians(lat)
        dlat = math.radians(lat - self.center[0])
        dlon = math.radians(lon - self.center[1])
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        
        return distance <= self.radius_km


class IsraelDroneRules:
    """
    Israeli drone operation rules
    Based on CAAI regulations
    """
    
    # Weight categories for Israel
    WEIGHT_LIMITS = {
        "registration_required": 0.25,  # kg - requires registration
        "license_required": 1.0,       # kg - requires operator license  
        "special_permit": 25.0          # kg - requires special permit
    }
    
    # Israel no-fly zones
    NO_FLY_ZONES = [
        # Ben Gurion Airport (TLV) - 4km radius
        IsraelNoFlyZone(
            name="Ben Gurion Airport",
            zone_type=IsraelZone.RESTRICTED,
            center=(32.0056, 34.8854),
            radius_km=4.0,
            description="4km radius, no drones above 30m"
        ),
        # Sde Dov (SDV) - old airport
        IsraelNoFlyZone(
            name="Sde Dov Airport",
            zone_type=IsraelZone.RESTRICTED,
            center=(32.0828, 34.8128),
            radius_km=2.0,
            description="2km radius around Sde Dov"
        ),
        # Haifa Airport
        IsraelNoFlyZone(
            name="Haifa Airport",
            zone_type=IsraelZone.RESTRICTED,
            center=(32.8114, 35.0431),
            radius_km=3.0,
            description="3km radius"
        ),
        # Ovda Airport
        IsraelNoFlyZone(
            name="Ovda Airport",
            zone_type=IsraelZone.RESTRICTED,
            center=(29.9406, 34.8169),
            radius_km=3.0,
            description="3km radius"
        ),
        # Gaza border - temporary restricted
        IsraelNoFlyZone(
            name="Gaza Border Area",
            zone_type=IsraelZone.RESTRICTED,
            center=(31.5, 34.4),
            radius_km=50.0,  # Large area
            max_altitude_m=50,
            description="Border area - check NOTAM before flight"
        ),
        # Military bases - approximate locations
        IsraelNoFlyZone(
            name="Tel Nof Military Base",
            zone_type=IsraelZone.RESTRICTED,
            center=(31.7333, 34.8333),
            radius_km=2.0,
            description="Military airbase"
        ),
        IsraelNoFlyZone(
            name="Nevatim Airbase",
            zone_type=IsraelZone.RESTRICTED,
            center=(31.2167, 34.9833),
            radius_km=2.0,
            description="Military airbase"
        ),
    ]
    
    # Maximum altitudes by zone
    ALTITUDE_LIMITS = {
        IsraelZone.OPEN: 120,       # meters
        IsraelZone.CONTROLLED: 50,
        IsraelZone.RESTRICTED: 0,
        IsraelZone.DANGEROUS: 30
    }
    
    # Allowed frequencies (matching CE)
    ALLOWED_FREQUENCIES = [
        # 2.4 GHz - up to 100mW
        {"band": "2.4 GHz", "min_mhz": 2400, "max_mhz": 24835, "max_mw": 100},
        # 5.8 GHz - up to 100mW
        {"band": "5.8 GHz", "min_mhz": 5725, "max_mhz": 5850, "max_mw": 100},
    ]
    
    @classmethod
    def check_no_fly_zone(
        cls,
        lat: float,
        lon: float,
        alt_m: float
    ) -> Tuple[bool, List[Dict]]:
        """
        Check if position is in any no-fly zone
        
        Returns:
            (is_safe, list of violated zones)
        """
        violations = []
        
        for zone in cls.NO_FLY_ZONES:
            if zone.contains_point(lat, lon):
                if alt_m <= zone.max_altitude_m:
                    violations.append({
                        "name": zone.name,
                        "type": zone.zone_type.value,
                        "radius_km": zone.radius_km,
                        "max_alt": zone.max_altitude_m,
                        "description": zone.description
                    })
                    
        return len(violations) == 0, violations
        
    @classmethod
    def get_flight_permission(
        cls,
        weight_kg: float,
        is_registered: bool,
        has_license: bool,
        alt_m: float
    ) -> Dict:
        """
        Get flight permission based on Israeli rules
        
        Returns:
            Dict with permission status and conditions
        """
        result = {
            "allowed": True,
            "conditions": [],
            "warnings": [],
            "errors": []
        }
        
        # Weight-based requirements
        if weight_kg > cls.WEIGHT_LIMITS["special_permit"]:
            result["errors"].append(f"Weight {weight_kg}kg requires special permit from CAAI")
            result["allowed"] = False
            
        elif weight_kg > cls.WEIGHT_LIMITS["license_required"]:
            if not has_license:
                result["errors"].append(f"Weight {weight_kg}kg requires operator license")
                result["allowed"] = False
            else:
                result["conditions"].append("Operator license required")
                
        elif weight_kg > cls.WEIGHT_LIMITS["registration_required"]:
            if not is_registered:
                result["errors"].append(f"Weight {weight_kg}kg requires registration")
                result["allowed"] = False
            else:
                result["conditions"].append("Registration required")
                
        # Altitude
        if alt_m > cls.ALTITUDE_LIMITS[IsraelZone.OPEN]:
            result["warnings"].append(f"Altitude {alt_m}m exceeds standard limit of {cls.ALTITUDE_LIMITS[IsraelZone.OPEN]}m")
            
        return result
        
    @classmethod
    def validate_frequency(
        cls,
        frequency_mhz: float,
        power_mw: float
    ) -> Tuple[bool, str]:
        """
        Validate frequency and power against Israeli rules
        
        Returns:
            (is_valid, reason)
        """
        for band in cls.ALLOWED_FREQUENCIES:
            if band["min_mhz"] <= frequency_mhz <= band["max_mhz"]:
                if power_mw <= band["max_mw"]:
                    return True, f"OK: {band['band']}, max {band['max_mw']}mW"
                else:
                    return False, f"Power {power_mw}mW exceeds {band['band']} limit of {band['max_mw']}mW"
                    
        return False, f"Frequency {frequency_mhz} MHz not in allowed bands"


class IsraelComplianceChecker:
    """
    Full compliance checker for Israeli regulations
    """
    
    def __init__(self):
        self.rules = IsraelDroneRules()
        self.checks = []
        
    def check_registration(
        self,
        weight_kg: float,
        is_registered: bool
    ) -> bool:
        """Check registration requirement"""
        requires_reg = weight_kg > 0.25
        
        if requires_reg and not is_registered:
            logger.warning(f"Weight {weight_kg}kg requires registration!")
            return False
            
        return True
        
    def check_airspace(
        self,
        lat: float,
        lon: float,
        alt_m: float
    ) -> Tuple[bool, List[Dict]]:
        """Check airspace restrictions"""
        safe, violations = self.rules.check_no_fly_zone(lat, lon, alt_m)
        
        if not safe:
            logger.warning(f"In no-fly zone! {len(violations)} violations")
            
        return safe, violations
        
    def check_operator_license(
        self,
        weight_kg: float,
        has_license: bool
    ) -> bool:
        """Check operator license requirement"""
        requires_license = weight_kg > 1.0
        
        if requires_license and not has_license:
            logger.warning(f"Weight {weight_kg}kg requires operator license!")
            return False
            
        return True
        
    def check_frequency(
        self,
        frequency_mhz: float,
        power_mw: float
    ) -> bool:
        """Check frequency compliance"""
        valid, reason = self.rules.validate_frequency(frequency_mhz, power_mw)
        
        if not valid:
            logger.warning(f"Frequency violation: {reason}")
            
        return valid
        
    def generate_report(self) -> str:
        """Generate compliance report"""
        report = []
        report.append("=" * 60)
        report.append("ISRAELI DRONE COMPLIANCE REPORT")
        report.append("CAAI / רשות התעופה האזרחית")
        report.append("=" * 60)
        report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("")
        report.append("Key Rules:")
        report.append(f"  Registration: >{self.rules.WEIGHT_LIMITS['registration_required']*1000}g")
        report.append(f"  License: >{self.rules.WEIGHT_LIMITS['license_required']*1000}g")
        report.append(f"  Special permit: >{self.rules.WEIGHT_LIMITS['special_permit']*1000}g")
        report.append("")
        report.append(f"No-Fly Zones: {len(self.rules.NO_FLY_ZONES)}")
        for zone in self.rules.NO_FLY_ZONES:
            report.append(f"  - {zone.name}: {zone.radius_km}km radius")
        report.append("")
        report.append("Allowed Frequencies:")
        for band in self.rules.ALLOWED_FREQUENCIES:
            report.append(f"  - {band['band']}: {band['max_mw']}mW max")
        report.append("=" * 60)
        return "\n".join(report)


# Example usage
if __name__ == "__main__":
    print("=" * 60)
    print("ISRAELI CFF COMPLIANCE TEST")
    print("רשות התעופה האזרחית")
    print("=" * 60)
    
    # Create checker
    checker = IsraelComplianceChecker()
    
    # Test drone specs
    drone = {
        "weight_kg": 0.9,
        "lat": 32.0853,
        "lon": 34.7818,
        "alt_m": 50,
        "frequency_mhz": 2400,
        "power_mw": 100,
        "is_registered": True,
        "has_license": False
    }
    
    print(f"\nDrone: {drone['weight_kg']}kg @ {drone['lat']},{drone['lon']},{drone['alt_m']}m")
    print(f"Frequency: {drone['frequency_mhz']} MHz @ {drone['power_mw']}mW")
    
    # Check all
    print("\nChecks:")
    
    # Registration
    reg_ok = checker.check_registration(drone['weight_kg'], drone['is_registered'])
    print(f"  Registration: {'OK' if reg_ok else 'FAIL'}")
    
    # License
    lic_ok = checker.check_operator_license(drone['weight_kg'], drone['has_license'])
    print(f"  License: {'OK' if lic_ok else 'FAIL'}")
    
    # Airspace
    safe, violations = checker.check_airspace(drone['lat'], drone['lon'], drone['alt_m'])
    print(f"  Airspace: {'OK' if safe else 'RESTRICTED'}")
    if violations:
        for v in violations:
            print(f"    - {v['name']}: {v['description']}")
    
    # Frequency
    freq_ok = checker.check_frequency(drone['frequency_mhz'], drone['power_mw'])
    print(f"  Frequency: {'OK' if freq_ok else 'FAIL'}")
    
    # Get permission
    print("\nFlight Permission:")
    perm = IsraelDroneRules.get_flight_permission(
        drone['weight_kg'],
        drone['is_registered'],
        drone['has_license'],
        drone['alt_m']
    )
    print(f"  Allowed: {perm['allowed']}")
    for cond in perm.get('conditions', []):
        print(f"    Condition: {cond}")
    for warn in perm.get('warnings', []):
        print(f"    Warning: {warn}")
    for err in perm.get('errors', []):
        print(f"    Error: {err}")
    
    # Generate report
    print("\n" + checker.generate_report())
    
    # Test Tel Aviv area
    print("\nTesting Tel Aviv area (32.0853, 34.7818):")
    safe, violations = IsraelDroneRules.check_no_fly_zone(32.0853, 34.7818, 50)
    if safe:
        print("  SAFE - No restrictions")
    else:
        print(f"  RESTRICTED - {len(violations)} zones")
        
    # Test Ben Gurion
    print("\nTesting Ben Gurion Airport (32.0056, 34.8854):")
    safe, violations = IsraelDroneRules.check_no_fly_zone(32.0056, 34.8854, 10)
    if safe:
        print("  SAFE")
    else:
        print(f"  RESTRICTED!")
        for v in violations:
            print(f"    - {v['name']}")