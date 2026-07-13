"""
SkyCore C-UAS Safety Integration

Connects C-UAS (threat prediction, airspace awareness, RF defense) to the
safety layer, enabling automatic protective actions when threats are detected.

This module acts as a bridge between:
- ThreatPredictor (trajectory prediction)
- AirspaceMonitor (ADS-B manned aircraft detection)
- RFScanner (jamming/spoofing detection)
- SafeDrone (safety wrapper)

When threats are detected at HIGH or CRITICAL level, automatic protective
actions are triggered: RTH, land, or hold position.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from cuas.threat_prediction import ThreatPredictor, PredictedThreat
from awareness.adsb import AirspaceMonitor, AirspaceAlert
from defense.rf_scanner import RFScanner, GPSIntegrityReport
from security.immutable_audit import log_security_event

log = logging.getLogger(__name__)


@dataclass
class SafetyThreat:
    """Unified threat from all C-UAS sources."""
    threat_type: str  # "aircraft_conflict", "hostile_drone", "jamming", "spoofing"
    threat_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    description: str
    source_module: str
    distance_m: Optional[float] = None
    time_to_closest_approach_s: Optional[float] = None
    recommended_action: str = "monitor"
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CUASSafetyIntegration:
    """Integrates C-UAS threat detection with safety system.
    
    Monitors all threat sources and triggers safety responses when needed.
    """

    def __init__(
        self,
        threat_predictor: Optional[ThreatPredictor] = None,
        airspace_monitor: Optional[AirspaceMonitor] = None,
        rf_scanner: Optional[RFScanner] = None,
        rth_on_high_threat: bool = True,
        land_on_critical_threat: bool = True,
    ):
        self.threat_predictor = threat_predictor or ThreatPredictor()
        self.airspace_monitor = airspace_monitor or AirspaceMonitor()
        self.rf_scanner = rf_scanner or RFScanner()
        
        # Configuration
        self.rth_on_high_threat = rth_on_high_threat
        self.land_on_critical_threat = land_on_critical_threat
        
        # State
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._current_threats: list[SafetyThreat] = []
        self._last_action_time: Optional[datetime] = None
        self._action_cooldown_s = 30.0  # Minimum time between automatic actions

        # Callbacks (to be set by integration)
        self._on_threat_detected: Optional[callable] = None
        self._on_safety_action: Optional[callable] = None

    def set_threat_callback(self, callback: callable) -> None:
        """Set callback for threat notifications."""
        self._on_threat_detected = callback

    def set_safety_action_callback(self, callback: callable) -> None:
        """Set callback for safety actions (RTH, land, etc.)."""
        self._on_safety_action = callback

    async def start_monitoring(
        self,
        drone_lat: float,
        drone_lon: float,
        drone_alt: float,
    ) -> None:
        """Start integrated threat monitoring."""
        self._monitoring = True
        
        # Start airspace monitoring
        await self.airspace_monitor.start(drone_lat, drone_lon, radius_km=10.0)
        
        # Start coordination loop
        self._monitor_task = asyncio.create_task(
            self._monitoring_loop(drone_lat, drone_lon, drone_alt)
        )
        
        log.info("C-UAS Safety Integration started")

    async def stop_monitoring(self) -> None:
        """Stop threat monitoring."""
        self._monitoring = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        await self.airspace_monitor.stop()
        log.info("C-UAS Safety Integration stopped")

    async def update_position(self, lat: float, lon: float, alt: float) -> None:
        """Update drone position for threat assessment."""
        self._last_drone_pos = (lat, lon, alt)

    async def _monitoring_loop(self, drone_lat: float, drone_lon: float, drone_alt: float) -> None:
        """Main monitoring loop - checks all threat sources."""
        while self._monitoring:
            try:
                threats = []
                
                # 1. Check ADS-B airspace alerts
                airspace_alerts = self.airspace_monitor.get_nearby(
                    drone_lat, drone_lon, drone_alt, radius_m=3000
                )
                for alert in airspace_alerts:
                    if alert.threat_level in ("HIGH", "CRITICAL"):
                        threats.append(SafetyThreat(
                            threat_type="aircraft_conflict",
                            threat_level=alert.threat_level,
                            description=f"ADS-B: {alert.aircraft.callsign or alert.aircraft.icao24} "
                                       f"{alert.distance_m:.0f}m away, {alert.time_to_closest_approach_s:.0f}s",
                            source_module="awareness",
                            distance_m=alert.distance_m,
                            time_to_closest_approach_s=alert.time_to_closest_approach_s,
                            recommended_action=alert.recommended_action,
                        ))

                # 2. Check hostile drone predictions
                predictions = self.threat_predictor.predict_all(
                    drone_lat, drone_lon, drone_alt, prediction_time_s=15.0
                )
                for pred in predictions:
                    if pred.threat_level in ("HIGH", "CRITICAL"):
                        threats.append(SafetyThreat(
                            threat_type="hostile_drone",
                            threat_level=pred.threat_level,
                            description=f"Threat {pred.drone_id}: {pred.intent}, "
                                       f"{pred.time_to_intercept_s:.0f}s to intercept",
                            source_module="cuas",
                            distance_m=pred.time_to_intercept_s * 10,  # Rough estimate
                            time_to_closest_approach_s=pred.time_to_intercept_s,
                            recommended_action=self._get_action_for_threat(pred.threat_level),
                        ))

                # 3. Check RF anomalies (GPS issues)
                # Note: Would need actual telemetry for this
                # scanner.check_gps_integrity(telemetry)

                # Update current threats
                self._current_threats = threats

                # Report threats
                if threats:
                    log.warning("C-UAS threats detected: %d", len(threats))
                    for t in threats:
                        log.warning("  [%s] %s", t.threat_level, t.description)
                        log_security_event("THREAT_DETECTED", t.__dict__, "CUAS")

                    # Trigger callback
                    if self._on_threat_detected:
                        try:
                            self._on_threat_detected(threats)
                        except Exception as e:
                            log.error("Threat callback error: %s", e)

                    # Automatic safety action
                    await self._evaluate_safety_action(threats)

                await asyncio.sleep(2.0)  # Check every 2 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Monitoring loop error: %s", e)
                await asyncio.sleep(5.0)

    async def _evaluate_safety_action(self, threats: list[SafetyThreat]) -> None:
        """Evaluate and execute safety actions based on threats."""
        if not threats:
            return

        # Check cooldown
        if self._last_action_time:
            elapsed = (datetime.utcnow() - self._last_action_time).total_seconds()
            if elapsed < self._action_cooldown_s:
                return

        # Determine worst threat level
        worst_level = max(t.threat_level for t in threats)
        
        if worst_level == "CRITICAL" and self.land_on_critical_threat:
            log.critical("CRITICAL THREAT - initiating emergency land")
            if self._on_safety_action:
                try:
                    await self._on_safety_action({"action": "land", "reason": "critical_threat"})
                    self._last_action_time = datetime.utcnow()
                    log_security_event("SAFETY_ACTION", {"action": "land", "reason": "critical_threat"}, "CUAS")
                except Exception as e:
                    log.error("Safety action failed: %s", e)
                    
        elif worst_level == "HIGH" and self.rth_on_high_threat:
            log.warning("HIGH THREAT - initiating RTH")
            if self._on_safety_action:
                try:
                    await self._on_safety_action({"action": "rth", "reason": "high_threat"})
                    self._last_action_time = datetime.utcnow()
                    log_security_event("SAFETY_ACTION", {"action": "rth", "reason": "high_threat"}, "CUAS")
                except Exception as e:
                    log.error("Safety action failed: %s", e)

    def _get_action_for_threat(self, threat_level: str) -> str:
        """Get recommended action for threat level."""
        if threat_level == "CRITICAL":
            return "emergency_land"
        elif threat_level == "HIGH":
            return "return_to_home"
        elif threat_level == "MEDIUM":
            return "hold_position"
        else:
            return "continue_mission"

    def get_current_threats(self) -> list[SafetyThreat]:
        """Get current active threats."""
        return self._current_threats.copy()

    def get_threat_summary(self) -> dict:
        """Get summary of threat status."""
        threats = self._current_threats
        
        by_type = {}
        by_level = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        
        for t in threats:
            by_type[t.threat_type] = by_type.get(t.threat_type, 0) + 1
            by_level[t.threat_level] += 1
        
        worst = "NONE"
        if by_level["CRITICAL"] > 0:
            worst = "CRITICAL"
        elif by_level["HIGH"] > 0:
            worst = "HIGH"
        elif by_level["MEDIUM"] > 0:
            worst = "MEDIUM"
        elif by_level["LOW"] > 0:
            worst = "LOW"
        
        return {
            "total_threats": len(threats),
            "worst_level": worst,
            "by_type": by_type,
            "by_level": by_level,
            "monitoring": self._monitoring,
        }

    def clear_threats(self) -> None:
        """Clear all tracked threats."""
        self._current_threats = []
        log.info("Threats cleared")


def integrate_cuas_with_safety(
    safety_wrapper,
    threat_predictor=None,
    airspace_monitor=None,
    rf_scanner=None,
) -> CUASSafetyIntegration:
    """Integrate C-UAS systems with SafeDrone wrapper.
    
    Returns configured integration that will trigger safety actions
    when threats are detected.
    """
    integration = CUASSafetyIntegration(
        threat_predictor=threat_predictor,
        airspace_monitor=airspace_monitor,
        rf_scanner=rf_scanner,
    )
    
    async def safety_action_handler(action: dict):
        action_type = action.get("action")
        if action_type == "land":
            await safety_wrapper.land()
        elif action_type == "rth":
            await safety_wrapper.return_to_home()
        elif action_type == "hold":
            await safety_wrapper.set_velocity(0, 0, 0, 0)
    
    integration.set_safety_action_callback(safety_action_handler)
    
    return integration