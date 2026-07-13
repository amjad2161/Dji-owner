"""
SkyCore CE/FCC Certification Compliance Module
============================================

Regulatory compliance for drone operations:
- CE (Europe) - EN 4709-001, EU Drone Regulation 2021/400
- FCC (USA) - Part 15, Part 90, Unmanned Aircraft Systems
- Israel (CAAI) - Civil Aviation Authority of Israel

Features:
- Frequency allocation checking
- Power limits validation
- Equipment classification
- Documentation generator
- Compliance reporting
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RegionType(Enum):
    """Radio regulatory regions"""
    EUROPE = "EU"      # CE
    USA = "US"         # FCC
    ISRAEL = "IL"      # CFF/CAAI
    UK = "UK"          # CAA
    GENERAL = "GEN"   # General


class DroneCategory(Enum):
    """EU Drone Categories (EASA)"""
    A1 = "A1"  # Open A1 - toys, <250g, no over people
    A2 = "A2"  # Open A2 - <2kg, safe distance
    A3 = "A3"  # Open A3 - <25kg, far from people
    SPECIFIC = "Specific"  # Requires authorization
    CERTIFIED = "Certified"  # Commercial, manned aircraft equivalent


class FrequencyBand(Enum):
    """Drone operating frequencies"""
    # 2.4 GHz (WiFi, common for drones)
    FREQ_2400_24835 = (2400, 24835, "2.4 GHz", 100, "Most common")
    
    # 5.8 GHz (WiFi, long range)
    FREQ_5725_5850 = (5725, 5850, "5.8 GHz", 500, "Long range")
    
    # 433 MHz (LPD433, short range)
    FREQ_43305_43479 = (433.05, 434.79, "433 MHz", 25, "Short range")
    
    # 868 MHz (Europe ISM)
    FREQ_863_870 = (863, 870, "868 MHz", 25, "Europe ISM")
    
    # 915 MHz (USA ISM)
    FREQ_902_928 = (902, 928, "915 MHz", 1000, "USA ISM")


@dataclass
class TransmitterSpec:
    """Transmitter specifications"""
    frequency_mhz: float
    power_dbm: float = 20  # dBm
    power_watt: float = 0.1  # Watts
    bandwidth_khz: int = 2000
    modulation: str = "FHSS"  # FHSS, DSSS, OFDM
    antenna_gain_dbi: float = 2.0


@dataclass
class EquipmentCertification:
    """Certification details"""
    region: RegionType
    certification_id: str
    certified_model: str
    manufacturer: str
    issued_date: datetime
    expiry_date: datetime
    max_tx_power_dbm: float
    frequency_bands: List[Tuple[float, float]]  # (min, max) MHz
    compliance_standards: List[str]
    restricted: bool = False
    restrictions: List[str] = field(default_factory=list)


@dataclass
class ComplianceCheck:
    """Compliance check result"""
    passed: bool
    rule: str
    requirement: str
    actual: Any
    limit: Any
    severity: str  # CRITICAL, WARNING, INFO


class CECertification:
    """
    CE Marking compliance for EU market
    Based on EU Drone Regulation 2021/400 (EASA)
    """
    
    # CE Drone weight categories
    WEIGHT_CATEGORIES = {
        "A1": {"max_weight": 0.25, "sub_250g": True},
        "A2": {"max_weight": 2.0, "sub_2kg": True},
        "A3": {"max_weight": 25.0, "sub_25kg": True},
        "Specific": {"max_weight": 100.0, "requires_author": True},
        "Certified": {"max_weight": float('inf'), "requires_type": True}
    }
    
    # Frequency power limits for CE (mW)
    FREQUENCY_LIMITS_CE = {
        # 2.4 GHz - SRD (Short Range Devices)
        (2400, 24835): {"max_mw": 100, "max_dbm": 20, "duty_cycle": 100},
        # 5.8 GHz - SRD
        (5725, 5875): {"max_mw": 1000, "max_dbm": 30, "duty_cycle": 100},
        # 868 MHz - Europe
        (863, 870): {"max_mw": 25, "max_dbm": 14.7, "duty_cycle": 1},
        # 433 MHz
        (433.05, 434.79): {"max_mw": 10, "max_dbm": 10, "duty_cycle": 10}
    }
    
    # EN 4709-001 standards for drone operations
    STANDARDS = {
        "EN4709-001": "UAS Command and Control",
        "EN4709-002": "UAS Communication",
        "EN4709-003": "UAS Identification",
        "EN303186": "Radio Equipment for drones"
    }
    
    def __init__(self):
        self.region = RegionType.EUROPE
        self.checks: List[ComplianceCheck] = []
        
    def check_weight_category(self, weight_kg: float) -> DroneCategory:
        """Determine CE drone category based on weight"""
        if weight_kg <= 0.25:
            return DroneCategory.A1
        elif weight_kg <= 2.0:
            return DroneCategory.A2
        elif weight_kg <= 25.0:
            return DroneCategory.A3
        else:
            return DroneCategory.SPECIFIC
            
    def check_transmitter_power(
        self,
        frequency_mhz: float,
        power_dbm: float
    ) -> ComplianceCheck:
        """Check if transmitter power complies with CE limits"""
        # Find applicable band
        for (f_min, f_max), limits in self.FREQUENCY_LIMITS_CE.items():
            if f_min <= frequency_mhz <= f_max:
                max_power_dbm = limits["max_dbm"]
                
                compliance = ComplianceCheck(
                    passed=power_dbm <= max_power_dbm,
                    rule="CE Power Limit",
                    requirement=f"Max {max_power_dbm} dBm for {f_min}-{f_max} MHz",
                    actual=f"{power_dbm} dBm ({10**(power_dbm/10)*1000:.1f} mW)",
                    limit=f"{max_power_dbm} dBm",
                    severity="CRITICAL" if power_dbm > max_power_dbm else "INFO"
                )
                self.checks.append(compliance)
                return compliance
                
        # Unknown frequency
        unknown = ComplianceCheck(
            passed=False,
            rule="Unknown Frequency",
            requirement="Frequency must be in approved bands",
            actual=f"{frequency_mhz} MHz",
            limit="Known band",
            severity="CRITICAL"
        )
        self.checks.append(unknown)
        return unknown
        
    def check_geo_awareness(self, has_geo_fence: bool) -> ComplianceCheck:
        """Check geo-awareness requirement"""
        # A2 and A3 require geo-awareness
        compliance = ComplianceCheck(
            passed=has_geo_fence,
            rule="Geo-awareness (A2/A3)",
            requirement="Geo-awareness system required",
            actual="Present" if has_geo_fence else "Missing",
            limit="Required",
            severity="WARNING" if not has_geo_fence else "INFO"
        )
        self.checks.append(compliance)
        return compliance
        
    def check_remote_id(self, has_rid: bool) -> ComplianceCheck:
        """Check Remote ID compliance (EU 2021/400)"""
        compliance = ComplianceCheck(
            passed=has_rid,
            rule="Remote ID",
            requirement="Direct Remote Identification required",
            actual="Present" if has_rid else "Missing",
            limit="Required for all categories",
            severity="CRITICAL" if not has_rid else "INFO"
        )
        self.checks.append(compliance)
        return compliance
        
    def generate_compliance_report(self) -> str:
        """Generate CE compliance report"""
        report = []
        report.append("=" * 60)
        report.append("CE COMPLIANCE REPORT")
        report.append("=" * 60)
        report.append(f"Region: {self.region.value}")
        report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("")
        
        passed = sum(1 for c in self.checks if c.passed)
        failed = len(self.checks) - passed
        
        report.append(f"Checks: {len(self.checks)}")
        report.append(f"  Passed: {passed}")
        report.append(f"  Failed: {failed}")
        report.append("")
        
        report.append("Results:")
        for check in self.checks:
            status = "[PASS]" if check.passed else "[FAIL]"
            report.append(f"  {status} {check.rule}")
            if not check.passed:
                report.append(f"       {check.requirement}")
                
        report.append("")
        if failed > 0:
            report.append("WARNING: Equipment not CE compliant!")
        else:
            report.append("Equipment is CE compliant.")
            
        report.append("=" * 60)
        return "\n".join(report)


class FCCCertification:
    """
    FCC Certification for USA market
    Based on Part 15, Part 90, and FAA UAS regulations
    """
    
    # FCC frequency bands for UAS
    FREQUENCY_LIMITS_FCC = {
        # 2.4 GHz ISM
        (2400, 24835): {"max_mw": 1000, "max_dbm": 30, "type": "Part 15.247"},
        # 5.8 GHz ISM
        (5725, 5875): {"max_mw": 1000, "max_dbm": 30, "type": "Part 15.247"},
        # 900 MHz ISM
        (902, 928): {"max_mw": 1000, "max_dbm": 30, "type": "Part 15.247"},
        # Part 90 (Business/Industrial)
        (809, 825): {"max_mw": 10000, "max_dbm": 40, "type": "Part 90"}
    }
    
    # FAA Remote ID requirements
    FAA_RID_SPECS = {
        "broadcast_range": 3,  # km
        "frequency": 920,  # MHz (UAS band)
        "update_rate": 1,  # Hz
        "message_format": "ASTM F3411"
    }
    
    def __init__(self):
        self.region = RegionType.USA
        self.checks: List[ComplianceCheck] = []
        
    def check_fcc_id(self, equipment_id: str) -> bool:
        """Verify FCC equipment ID exists"""
        # In real impl, check FCC database
        # Format: FCC ID like "ABC123456"
        return len(equipment_id) >= 8
        
    def check_frequency_allocation(
        self,
        frequency_mhz: float,
        max_power_dbm: float
    ) -> ComplianceCheck:
        """Check frequency and power against FCC rules"""
        for (f_min, f_max), limits in self.FREQUENCY_LIMITS_FCC.items():
            if f_min <= frequency_mhz <= f_max:
                max_power = limits["max_dbm"]
                
                compliance = ComplianceCheck(
                    passed=max_power_dbm <= max_power,
                    rule=f"FCC {limits['type']}",
                    requirement=f"Max {max_power} dBm for {f_min}-{f_max} MHz",
                    actual=f"{max_power_dbm} dBm",
                    limit=f"{max_power} dBm",
                    severity="CRITICAL" if max_power_dbm > max_power else "INFO"
                )
                self.checks.append(compliance)
                return compliance
                
        # Amateur radio or not permitted
        unknown = ComplianceCheck(
            passed=False,
            rule="Frequency Allocation",
            requirement="Must be in licensed band",
            actual=f"{frequency_mhz} MHz",
            limit="Licensed band",
            severity="CRITICAL"
        )
        self.checks.append(unknown)
        return unknown
        
    def check_ham_license(
        self,
        is_amateur_band: bool,
        has_license: bool = True
    ) -> ComplianceCheck:
        """Check amateur radio license requirements"""
        if is_amateur_band and not has_license:
            compliance = ComplianceCheck(
                passed=False,
                rule="Amateur License",
                requirement="HAM license required for amateur bands",
                actual="No license",
                limit="Required",
                severity="CRITICAL"
            )
        else:
            compliance = ComplianceCheck(
                passed=True,
                rule="Amateur License",
                requirement="No license required (or licensed)",
                actual="OK",
                limit="N/A",
                severity="INFO"
            )
        self.checks.append(compliance)
        return compliance
        
    def generate_compliance_report(self) -> str:
        """Generate FCC compliance report"""
        report = []
        report.append("=" * 60)
        report.append("FCC COMPLIANCE REPORT")
        report.append("=" * 60)
        report.append(f"Region: {self.region.value}")
        report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("")
        
        passed = sum(1 for c in self.checks if c.passed)
        failed = len(self.checks) - passed
        
        report.append(f"Checks: {len(self.checks)}")
        report.append(f"  Passed: {passed}")
        report.append(f"  Failed: {failed}")
        report.append("")
        
        for check in self.checks:
            status = "[PASS]" if check.passed else "[FAIL]"
            report.append(f"  {status} {check.rule}")
            
        report.append("")
        if failed > 0:
            report.append("WARNING: Equipment not FCC compliant!")
        else:
            report.append("Equipment is FCC compliant.")
            
        report.append("=" * 60)
        return "\n".join(report)


class IsraelCAACompliance:
    """
    Civil Aviation Authority of Israel (CAAI) compliance
    Israeli drone regulations
    """
    
    def __init__(self):
        self.region = RegionType.ISRAEL
        self.checks: List[ComplianceCheck] = []
        
    def check_registration(self, is_registered: bool, weight_kg: float) -> ComplianceCheck:
        """Check Israeli registration requirement"""
        # Israel requires registration for >250g
        requires_reg = weight_kg > 0.25
        
        compliance = ComplianceCheck(
            passed=not requires_reg or is_registered,
            rule="Israeli Registration",
            requirement=f"Registration required for >250g drones",
            actual="Registered" if is_registered else "Not registered",
            limit="Required" if requires_reg else "Not required",
            severity="CRITICAL" if requires_reg and not is_registered else "INFO"
        )
        self.checks.append(compliance)
        return compliance
        
    def check_no_fly_zones(self, lat: float, lon: float) -> Tuple[bool, List[str]]:
        """
        Check Israeli no-fly zones
        Main areas: Ben Gurion Airport, military bases, Gaza border
        """
        violations = []
        
        # Example no-fly zones (simplified)
        ben_gurion = (32.0056, 34.8854)  # Airport
        # Check distance from Ben Gurion
        # In real impl, check actual restricted airspace
        
        return len(violations) == 0, violations
        
    def check_frequencies(self, frequency_mhz: float, power_dbm: float) -> ComplianceCheck:
        """Check Israeli frequency allocation"""
        # Israel follows CE for most drone frequencies
        # But has specific allocations
        
        # Allowed frequencies
        allowed = [
            (2400, 24835, 100),  # 2.4 GHz, 100 mW
            (5725, 5875, 100),   # 5.8 GHz, 100 mW
            (915, 920, 1000),     # 900 MHz, 1W (with license)
        ]
        
        is_allowed = False
        max_power = 0
        
        for f_min, f_max, power in allowed:
            if f_min <= frequency_mhz <= f_max:
                is_allowed = True
                max_power = power
                break
                
        compliance = ComplianceCheck(
            passed=is_allowed and power_dbm <= 10 * (max_power > 0),
            rule="Frequency Allocation",
            requirement=f"Allowed: 2.4GHz (<100mW), 5.8GHz (<100mW), 900MHz (<1W with license)",
            actual=f"{frequency_mhz} MHz, {power_dbm} dBm",
            limit=f"Max {max_power} mW" if is_allowed else "Not allowed",
            severity="CRITICAL" if not is_allowed else "WARNING"
        )
        self.checks.append(compliance)
        return compliance


class ComplianceManager:
    """
    Unified compliance manager for all regions
    """
    
    def __init__(self):
        self.ce = CECertification()
        self.fcc = FCCCertification()
        self.il = IsraelCAACompliance()
        
        self.current_region: RegionType = RegionType.GENERAL
        
    def set_region(self, region: RegionType):
        """Set current compliance region"""
        self.current_region = region
        
    def check_all(
        self,
        weight_kg: float,
        frequency_mhz: float,
        power_dbm: float,
        has_remote_id: bool = False,
        has_geo_fence: bool = False,
        is_registered: bool = False
    ) -> Dict[str, ComplianceCheck]:
        """Run all compliance checks"""
        results = {}
        
        # CE checks
        results['ce_category'] = self.ce.check_weight_category(weight_kg)
        results['ce_power'] = self.ce.check_transmitter_power(frequency_mhz, power_dbm)
        results['ce_remote_id'] = self.ce.check_remote_id(has_remote_id)
        results['ce_geo'] = self.ce.check_geo_awareness(has_geo_fence)
        
        # FCC checks
        results['fcc_frequency'] = self.fcc.check_frequency_allocation(frequency_mhz, power_dbm)
        
        # Israel checks
        results['il_registration'] = self.il.check_registration(is_registered, weight_kg)
        results['il_frequency'] = self.il.check_frequencies(frequency_mhz, power_dbm)
        
        return results
        
    def generate_report(self, region: RegionType = None) -> str:
        """Generate compliance report for region"""
        if region == RegionType.EUROPE:
            return self.ce.generate_compliance_report()
        elif region == RegionType.USA:
            return self.fcc.generate_compliance_report()
        elif region == RegionType.ISRAEL:
            return self.il.generate_compliance_report()
        else:
            # Generate all
            return self.ce.generate_compliance_report() + "\n\n" + \
                   self.fcc.generate_compliance_report() + "\n\n" + \
                   self.il.generate_compliance_report()


class FrequencyAnalyzer:
    """
    Analyze frequency compatibility
    """
    
    # Channel plans for common protocols
    CHANNEL_PLANS = {
        "DJI": {
            "2.4G": [(2400 + i * 5, 2500) for i in range(8)],  # 2400-2480
            "5.8G": [(5725 + i * 10, 5850) for i in range(8)]   # 5725-5850
        },
        "DJI O3": {
            "2.4G": [(2400, 2483)],
            "5.8G": [(5725, 5830)],
            "AFH": [(5735, 5830)]
        },
        "MAVLink": {
            "915MHz": [(902, 928)]
        },
        "ExpressLRS": {
            "900MHz": [(902, 928)],
            "2.4G": [(2400, 2480)],
            "5.8G": [(5725, 5850)]
        }
    }
    
    @staticmethod
    def get_safe_frequencies(
        region: RegionType,
        max_power_mw: float
    ) -> List[Dict]:
        """Get safe frequencies for region"""
        safe = []
        
        if region in [RegionType.EUROPE, RegionType.ISRAEL]:
            safe.extend([
                {"band": "2.4 GHz", "min": 2400, "max": 24835, "max_mw": min(100, max_power_mw)},
                {"band": "5.8 GHz", "min": 5725, "max": 5850, "max_mw": min(100, max_power_mw)}
            ])
            
        if region == RegionType.USA:
            safe.extend([
                {"band": "2.4 GHz", "min": 2400, "max": 24835, "max_mw": min(1000, max_power_mw)},
                {"band": "5.8 GHz", "min": 5725, "max": 5850, "max_mw": min(1000, max_power_mw)},
                {"band": "900 MHz", "min": 902, "max": 928, "max_mw": min(1000, max_power_mw)}
            ])
            
        return safe
        
    @staticmethod
    def check_interference(
        frequency_mhz: float,
        nearby_freqs: List[float],
        min_separation_mhz: float = 5.0
    ) -> Tuple[bool, List[float]]:
        """Check for interference with nearby frequencies"""
        conflicts = []
        
        for freq in nearby_freqs:
            if abs(frequency_mhz - freq) < min_separation_mhz:
                conflicts.append(freq)
                
        return len(conflicts) == 0, conflicts


# Example usage
if __name__ == "__main__":
    print("=" * 60)
    print("SKYCORE COMPLIANCE MODULE TEST")
    print("=" * 60)
    
    # Create compliance manager
    manager = ComplianceManager()
    
    # Test equipment specs
    drone = {
        "weight_kg": 0.9,
        "frequency_mhz": 2400,
        "power_dbm": 20,
        "has_remote_id": True,
        "has_geo_fence": True,
        "is_registered": True
    }
    
    print("\nDrone Specifications:")
    print(f"  Weight: {drone['weight_kg']} kg")
    print(f"  Frequency: {drone['frequency_mhz']} MHz")
    print(f"  Power: {drone['power_dbm']} dBm")
    print(f"  Remote ID: {drone['has_remote_id']}")
    print(f"  Geo-fence: {drone['has_geo_fence']}")
    
    # Run compliance checks
    print("\nRunning compliance checks...")
    results = manager.check_all(**drone)
    
    print("\nResults:")
    for check_name, result in results.items():
        # Handle both DroneCategory and ComplianceCheck
        if hasattr(result, 'passed'):
            status = "PASS" if result.passed else "FAIL"
            print(f"  [{status}] {check_name}: {result.rule}")
        else:
            # DroneCategory enum
            print(f"  [INFO] {check_name}: Category = {result}")
        
    # Generate CE report
    print("\n" + "=" * 60)
    print(manager.ce.generate_compliance_report())
    
    # Safe frequencies
    print("\nSafe frequencies for EU:")
    safe = FrequencyAnalyzer.get_safe_frequencies(RegionType.EUROPE, 100)
    for band in safe:
        print(f"  {band['band']}: {band['min']}-{band['max']} MHz (max {band['max_mw']} mW)")
        
    # Safe frequencies for USA
    print("\nSafe frequencies for USA:")
    safe_us = FrequencyAnalyzer.get_safe_frequencies(RegionType.USA, 1000)
    for band in safe_us:
        print(f"  {band['band']}: {band['min']}-{band['max']} MHz (max {band['max_mw']} mW)")