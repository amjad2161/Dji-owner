"""
SkyCore Defense Layer - Pre-flight RF & Signal Analysis

Detects potential interference, jamming attempts, and signal anomalies
in the operating environment before and during flight.

Capabilities:
- RF spectrum scanning (detection only - no transmission)
- GPS integrity verification
- Jamming/spoofing detection
- Signal anomaly alerting
- Multi-sensor threat fusion

This is a DEFENSIVE system - detection only, no jamming, no transmission.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class SignalReading:
    """Single signal measurement."""
    timestamp: datetime
    frequency_hz: float
    strength_dbm: float
    bandwidth_hz: Optional[float] = None
    modulation: Optional[str] = None
    source: str = "unknown"  # "adsb", "dji", "wifi", "unknown"


@dataclass
class SignalAnomaly:
    """Detected signal anomaly."""
    anomaly_type: str  # "jamming", "spoofing", "interference", "unauthorized"
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    confidence: float  # 0-1
    description: str
    affected_frequency_hz: Optional[float] = None
    recommended_action: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GPSIntegrityReport:
    """GPS signal health report."""
    is_valid: bool
    satellites_tracked: int
    signal_quality: str  # EXCELLENT, GOOD, FAIR, POOR, INVALID
    anomalies: list[str] = field(default_factory=list)
    spoofing_indicators: list[str] = field(default_factory=list)
    recommendation: str = ""


class RFScanner:
    """RF signal scanner for pre-flight environment assessment.
    
    NOTE: This is detection/monitoring only. No transmission or jamming.
    Uses available receiver hardware (RTL-SDR, integrated WiFi, etc.)
    """

    def __init__(self):
        self._readings: list[SignalReading] = []
        self._anomalies: list[SignalAnomaly] = []
        self._monitoring = False

    async def scan_environment(self, duration_s: float = 10.0) -> dict:
        """Perform environment scan and return analysis.
        
        Args:
            duration_s: How long to scan
            
        Returns:
            dict with scan results and recommendations
        """
        log.info("Starting RF environment scan (%ds duration)", duration_s)
        start = time.time()
        readings = []
        
        # Simulate scanning (real implementation would use RTL-SDR, etc.)
        # This represents the detection of common drone control frequencies
        scan_frequencies = [
            (2400_000_000, "2.4 GHz", "DJI/WiFi"),
            (5725_000_000, "5.8 GHz", "DJI/FPV"),
            (1090_000_000, "1090 MHz", "ADS-B"),
        ]
        
        while time.time() - start < duration_s:
            for freq, label, source in scan_frequencies:
                # Simulate signal strength readings
                strength = self._simulate_signal_strength(freq, source)
                readings.append(SignalReading(
                    timestamp=datetime.utcnow(),
                    frequency_hz=freq,
                    strength_dbm=strength,
                    source=source,
                ))
            await asyncio.sleep(0.5)
        
        self._readings.extend(readings)
        
        # Analyze results
        return self._analyze_scan(readings)

    def _simulate_signal_strength(self, freq: int, source: str) -> float:
        """Simulate signal strength (in real use, this would read from hardware)."""
        import random
        # Baseline noise floor around -90 dBm
        base = -90
        
        if source == "DJI/WiFi":
            # Common in populated areas
            base = random.uniform(-85, -65)
        elif source == "DJI/FPV":
            base = random.uniform(-90, -70)
        elif source == "ADS-B":
            base = random.uniform(-95, -80)
        
        return base

    def _analyze_scan(self, readings: list[SignalReading]) -> dict:
        """Analyze readings for anomalies."""
        results = {
            "scan_duration_s": len(readings) / 5,  # rough estimate
            "readings_count": len(readings),
            "signals_detected": {},
            "anomalies": [],
            "recommendation": "CLEAR",
            "overall_status": "OK",
        }
        
        # Aggregate by frequency
        for r in readings:
            key = f"{r.frequency_hz/1e6:.0f} MHz"
            if key not in results["signals_detected"]:
                results["signals_detected"][key] = []
            results["signals_detected"][key].append(r.strength_dbm)
        
        # Calculate averages
        for key, strengths in results["signals_detected"].items():
            results["signals_detected"][key] = {
                "avg_dbm": sum(strengths) / len(strengths),
                "max_dbm": max(strengths),
                "samples": len(strengths),
            }
        
        # Check for anomalies
        # High signal on 2.4GHz might indicate DJI controller nearby
        if "2400 MHz" in results["signals_detected"]:
            avg = results["signals_detected"]["2400 MHz"]["avg_dbm"]
            if avg > -60:
                results["anomalies"].append({
                    "type": "strong_signal",
                    "description": f"Strong 2.4GHz signal ({avg:.1f} dBm) - likely DJI controller nearby",
                    "severity": "INFO",
                })
        
        # Determine overall status
        if any(a.get("severity") == "HIGH" for a in results["anomalies"]):
            results["overall_status"] = "WARNING"
            results["recommendation"] = "Review environment before flight"
        elif any(a.get("severity") == "CRITICAL" for a in results["anomalies"]):
            results["overall_status"] = "ALERT"
            results["recommendation"] = "Do not fly - potential interference detected"
        
        return results

    def check_gps_integrity(self, telemetry) -> GPSIntegrityReport:
        """Check GPS signal integrity from telemetry.
        
        Detects potential spoofing based on:
        - Sudden position jumps
        - Velocity inconsistencies
        - Signal quality metrics
        """
        anomalies = []
        spoofing_indicators = []
        
        gps_sats = getattr(telemetry, 'gps_satellites', 0)
        signal_strength = getattr(telemetry, 'signal_strength', 100)
        
        # Low satellite count
        if gps_sats < 8:
            anomalies.append(f"Low satellite count: {gps_sats}")
        
        if gps_sats < 4:
            anomalies.append("GPS unreliable - insufficient satellites")
            spoofing_indicators.append("Critical satellite deprivation")
        
        # Low signal strength
        if signal_strength < 50:
            anomalies.append(f"Weak signal: {signal_strength}%")
        
        if signal_strength < 30:
            spoofing_indicators.append("Signal degradation detected")
        
        # Determine quality
        if gps_sats >= 12 and signal_strength >= 80:
            quality = "EXCELLENT"
        elif gps_sats >= 8 and signal_strength >= 60:
            quality = "GOOD"
        elif gps_sats >= 6:
            quality = "FAIR"
        elif gps_sats >= 4:
            quality = "POOR"
        else:
            quality = "INVALID"
        
        is_valid = len(anomalies) == 0 or quality not in ("POOR", "INVALID")
        
        recommendation = {
            "EXCELLENT": "GPS optimal for flight",
            "GOOD": "GPS suitable for flight",
            "FAIR": "GPS acceptable with caution",
            "POOR": "Consider delay - GPS marginal",
            "INVALID": "Do not fly - GPS unreliable",
        }.get(quality, "Unknown")
        
        return GPSIntegrityReport(
            is_valid=is_valid,
            satellites_tracked=gps_sats,
            signal_quality=quality,
            anomalies=anomalies,
            spoofing_indicators=spoofing_indicators,
            recommendation=recommendation,
        )

    def detect_jamming_pattern(self, recent_readings: list[float]) -> Optional[SignalAnomaly]:
        """Detect potential jamming based on sudden signal loss.
        
        Args:
            recent_readings: List of signal strength readings over time
        
        Returns:
            SignalAnomaly if jamming detected, None otherwise
        """
        if len(recent_readings) < 5:
            return None
        
        # Calculate rate of change
        changes = [recent_readings[i] - recent_readings[i-1] 
                   for i in range(1, len(recent_readings))]
        
        avg_change = sum(changes) / len(changes)
        
        # Sudden drop (>10 dBm per reading) could indicate jamming
        if all(c < -10 for c in changes[-3:]):
            return SignalAnomaly(
                anomaly_type="jamming",
                severity="HIGH",
                confidence=0.85,
                description="Sudden signal degradation pattern - possible jamming",
                recommended_action="Initiate RTH immediately, report to operator",
            )
        
        # Persistent low signal
        if all(r < -100 for r in recent_readings[-5:]):
            return SignalAnomaly(
                anomaly_type="interference",
                severity="MEDIUM",
                confidence=0.70,
                description="Consistently low signal strength - interference or range limit",
                recommended_action="Reduce distance, check for obstacles",
            )
        
        return None

    def detect_spoofing(self, position_history: list[tuple[float, float]]) -> Optional[SignalAnomaly]:
        """Detect potential GPS spoofing based on position jumps.
        
        Args:
            position_history: List of (lat, lon) readings over time
        """
        if len(position_history) < 3:
            return None
        
        # Calculate jumps between consecutive readings
        for i in range(1, len(position_history)):
            dist = self._haversine_m(
                position_history[i-1][0], position_history[i-1][1],
                position_history[i][0], position_history[i][1],
            )
            # Unreasonable jump (>100m in 1 second) indicates spoofing
            if dist > 100:
                return SignalAnomaly(
                    anomaly_type="spoofing",
                    severity="CRITICAL",
                    confidence=0.90,
                    description=f"GPS position jump detected: {dist:.0f}m in one reading",
                    recommended_action="Ground immediately, possible GPS attack",
                )
        
        return None

    def _haversine_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance in meters."""
        import math
        R = 6371000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


# Global scanner instance
default_scanner = RFScanner()


async def preflight_signal_check(lat: float, lon: float) -> dict:
    """Quick pre-flight check for signal environment.
    
    Returns:
        dict with status and recommendations
    """
    scanner = RFScanner()
    rf_results = await scanner.scan_environment(duration_s=5.0)
    
    return {
        "status": rf_results["overall_status"],
        "rf_environment": rf_results,
        "recommendation": rf_results["recommendation"],
        "signals_detected": list(rf_results["signals_detected"].keys()),
    }