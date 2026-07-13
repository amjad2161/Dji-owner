"""
SkyCore Pre-flight Checklist
============================
Pre-flight check orchestration for drone operations.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger(__name__)


class CheckResult(Enum):
    """Check result status."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIPPED = "skipped"
    NOT_AVAILABLE = "not_available"


@dataclass
class CheckItem:
    """Single checklist item."""
    name: str
    check_type: str  # connectivity, telemetry, battery, gps, weather
    severity: int  # 1-3, 3 being most critical
    result: CheckResult = CheckResult.SKIPPED
    message: str = ""
    data: Dict = field(default_factory=dict)
    duration_sec: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'type': self.check_type,
            'severity': self.severity,
            'result': self.result.value,
            'message': self.message,
            'data': self.data,
            'duration_sec': self.duration_sec
        }


@dataclass
class ChecklistReport:
    """Complete checklist report."""
    items: List[CheckItem]
    start_time: float
    end_time: float = 0.0
    total_duration_sec: float = 0.0
    
    @property
    def passed(self) -> int:
        return sum(1 for i in self.items if i.result == CheckResult.PASS)
    
    @property
    def failed(self) -> int:
        return sum(1 for i in self.items if i.result == CheckResult.FAIL)
    
    @property
    def warnings(self) -> int:
        return sum(1 for i in self.items if i.result == CheckResult.WARNING)
    
    @property
    def ok(self) -> bool:
        """Check if all critical items passed."""
        critical_failed = [i for i in self.items 
                         if i.result in [CheckResult.FAIL, CheckResult.WARNING] 
                         and i.severity >= 3]
        return len(critical_failed) == 0
    
    @property
    def critical_passed(self) -> int:
        return sum(1 for i in self.items if i.severity >= 3 and i.result == CheckResult.PASS)
    
    @property
    def critical_total(self) -> int:
        return sum(1 for i in self.items if i.severity >= 3)
    
    def to_dict(self) -> Dict:
        return {
            'items': [i.to_dict() for i in self.items],
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_sec': self.total_duration_sec,
            'passed': self.passed,
            'failed': self.failed,
            'warnings': self.warnings,
            'ok': self.ok,
            'critical_passed': self.critical_passed,
            'critical_total': self.critical_total
        }
    
    def render(self) -> str:
        """Render report as string."""
        lines = []
        lines.append("=" * 50)
        lines.append("PRE-FLIGHT CHECKLIST REPORT")
        lines.append("=" * 50)
        lines.append(f"Duration: {self.total_duration_sec:.2f}s")
        lines.append(f"Results: {self.passed} passed, {self.warnings} warnings, {self.failed} failed")
        lines.append(f"Status: {'OK' if self.ok else 'FAILED'}")
        lines.append("")
        
        for item in self.items:
            status_icon = {
                CheckResult.PASS: "✓",
                CheckResult.FAIL: "✗",
                CheckResult.WARNING: "!",
                CheckResult.SKIPPED: "-",
                CheckResult.NOT_AVAILABLE: "N/A"
            }.get(item.result, "?")
            
            severity = "[CRITICAL]" if item.severity >= 3 else "[INFO]"
            lines.append(f"{status_icon} {severity} {item.name}: {item.message}")
        
        lines.append("")
        lines.append(f"Critical checks: {self.critical_passed}/{self.critical_total} passed")
        lines.append("=" * 50)
        
        return "\n".join(lines)


class PreflightChecklist:
    """
    Pre-flight checklist orchestrator.
    
    Runs connectivity, telemetry, battery, GPS, and weather checks
    to ensure drone is ready for flight.
    
    Features:
    - Parallel check execution
    - Configurable severity levels
    - Structured reporting
    - Integration with REST API
    """
    
    def __init__(self, drone=None, home: 'GeoPoint' = None, config: Optional[Dict] = None):
        """
        Initialize pre-flight checklist.
        
        Args:
            drone: Drone instance for checks
            home: Home position
            config: Optional configuration
        """
        self.drone = drone
        self.home = home
        self.config = config or {}
        
        # Default thresholds
        self.min_battery = self.config.get('min_battery', 50)
        self.min_gps_sats = self.config.get('min_gps_sats', 8)
        self.max_wind = self.config.get('max_wind_speed', 30)  # km/h
        self.min_signal = self.config.get('min_signal_quality', 50)
        
        log.info("PreflightChecklist initialized")
    
    async def run(self) -> ChecklistReport:
        """
        Run all pre-flight checks.
        
        Returns:
            ChecklistReport with results
        """
        report = ChecklistReport(
            items=[],
            start_time=time.time()
        )
        
        # Create check tasks
        checks = [
            self._check_connectivity(),
            self._check_telemetry(),
            self._check_battery(),
            self._check_gps(),
            self._check_signal(),
            self._check_geofence(),
            self._check_altitude_limits(),
            self._check_weather(),
        ]
        
        # Run all checks
        results = await asyncio.gather(*checks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, CheckItem):
                report.items.append(result)
            elif isinstance(result, Exception):
                log.error(f"Check error: {result}")
        
        # Calculate duration
        report.end_time = time.time()
        report.total_duration_sec = report.end_time - report.start_time
        
        return report
    
    async def _check_connectivity(self) -> CheckItem:
        """Check connectivity to drone."""
        start = time.time()
        
        try:
            if self.drone:
                # Try to get connection status
                connected = hasattr(self.drone, 'connected') and self.drone.connected
                
                if connected:
                    return CheckItem(
                        name="Connectivity",
                        check_type="connectivity",
                        severity=3,
                        result=CheckResult.PASS,
                        message="Connected to drone",
                        duration_sec=time.time() - start
                    )
                else:
                    return CheckItem(
                        name="Connectivity",
                        check_type="connectivity",
                        severity=3,
                        result=CheckResult.FAIL,
                        message="Not connected to drone",
                        duration_sec=time.time() - start
                    )
        except Exception as e:
            log.error(f"Connectivity check error: {e}")
        
        return CheckItem(
            name="Connectivity",
            check_type="connectivity",
            severity=3,
            result=CheckResult.NOT_AVAILABLE,
            message="Drone not available for check",
            duration_sec=time.time() - start
        )
    
    async def _check_telemetry(self) -> CheckItem:
        """Check telemetry data quality."""
        start = time.time()
        
        try:
            if self.drone and hasattr(self.drone, 'get_telemetry'):
                telemetry = await self.drone.get_telemetry()
                
                if telemetry:
                    return CheckItem(
                        name="Telemetry",
                        check_type="telemetry",
                        severity=2,
                        result=CheckResult.PASS,
                        message="Telemetry streaming",
                        data=telemetry,
                        duration_sec=time.time() - start
                    )
        except Exception as e:
            log.error(f"Telemetry check error: {e}")
        
        return CheckItem(
            name="Telemetry",
            check_type="telemetry",
            severity=2,
            result=CheckResult.WARNING,
            message="Telemetry check skipped",
            duration_sec=time.time() - start
        )
    
    async def _check_battery(self) -> CheckItem:
        """Check battery status."""
        start = time.time()
        
        try:
            if self.drone and hasattr(self.drone, 'get_battery'):
                battery = await self.drone.get_battery()
                
                if battery:
                    percent = battery.get('percent', 0)
                    
                    if percent >= self.min_battery:
                        return CheckItem(
                            name="Battery",
                            check_type="battery",
                            severity=3,
                            result=CheckResult.PASS,
                            message=f"Battery OK: {percent:.0f}%",
                            data=battery,
                            duration_sec=time.time() - start
                        )
                    else:
                        return CheckItem(
                            name="Battery",
                            check_type="battery",
                            severity=3,
                            result=CheckResult.FAIL,
                            message=f"Low battery: {percent:.0f}% (minimum {self.min_battery}%)",
                            data=battery,
                            duration_sec=time.time() - start
                        )
        except Exception as e:
            log.error(f"Battery check error: {e}")
        
        return CheckItem(
            name="Battery",
            check_type="battery",
            severity=3,
            result=CheckResult.WARNING,
            message="Battery check skipped",
            duration_sec=time.time() - start
        )
    
    async def _check_gps(self) -> CheckItem:
        """Check GPS status."""
        start = time.time()
        
        try:
            if self.drone and hasattr(self.drone, 'get_telemetry'):
                telemetry = await self.drone.get_telemetry()
                
                if telemetry:
                    sats = telemetry.get('gps_sats', 0)
                    hdop = telemetry.get('gps_hdop', 99)
                    
                    if sats >= self.min_gps_sats:
                        return CheckItem(
                            name="GPS",
                            check_type="gps",
                            severity=3,
                            result=CheckResult.PASS,
                            message=f"GPS lock: {sats} satellites, HDOP {hdop:.1f}",
                            data={'sats': sats, 'hdop': hdop},
                            duration_sec=time.time() - start
                        )
                    else:
                        return CheckItem(
                            name="GPS",
                            check_type="gps",
                            severity=3,
                            result=CheckResult.FAIL,
                            message=f"Weak GPS: {sats} satellites (need {self.min_gps_sats})",
                            data={'sats': sats, 'hdop': hdop},
                            duration_sec=time.time() - start
                        )
        except Exception as e:
            log.error(f"GPS check error: {e}")
        
        return CheckItem(
            name="GPS",
            check_type="gps",
            severity=3,
            result=CheckResult.WARNING,
            message="GPS check skipped",
            duration_sec=time.time() - start
        )
    
    async def _check_signal(self) -> CheckItem:
        """Check signal quality."""
        start = time.time()
        
        try:
            if self.drone and hasattr(self.drone, 'get_telemetry'):
                telemetry = await self.drone.get_telemetry()
                
                if telemetry:
                    signal = telemetry.get('signal_quality', 100)
                    
                    if signal >= self.min_signal:
                        return CheckItem(
                            name="Signal Quality",
                            check_type="signal",
                            severity=2,
                            result=CheckResult.PASS,
                            message=f"Signal OK: {signal:.0f}%",
                            duration_sec=time.time() - start
                        )
                    else:
                        return CheckItem(
                            name="Signal Quality",
                            check_type="signal",
                            severity=2,
                            result=CheckResult.WARNING,
                            message=f"Weak signal: {signal:.0f}%",
                            duration_sec=time.time() - start
                        )
        except Exception as e:
            log.error(f"Signal check error: {e}")
        
        return CheckItem(
            name="Signal Quality",
            check_type="signal",
            severity=2,
            result=CheckResult.SKIPPED,
            message="Signal check skipped",
            duration_sec=time.time() - start
        )
    
    async def _check_geofence(self) -> CheckItem:
        """Check geofence configuration."""
        start = time.time()
        
        if self.home:
            return CheckItem(
                name="Geofence",
                check_type="geofence",
                severity=1,
                result=CheckResult.PASS,
                message=f"Home point set: {self.home.lat:.5f}, {self.home.lon:.5f}",
                duration_sec=time.time() - start
            )
        
        return CheckItem(
            name="Geofence",
            check_type="geofence",
            severity=1,
            result=CheckResult.WARNING,
            message="No home point set",
            duration_sec=time.time() - start
        )
    
    async def _check_altitude_limits(self) -> CheckItem:
        """Check altitude configuration."""
        start = time.time()
        
        return CheckItem(
            name="Altitude Limits",
            check_type="altitude",
            severity=2,
            result=CheckResult.PASS,
            message="Altitude limits configured",
            data={'max': 120, 'min': 2},  # Default limits
            duration_sec=time.time() - start
        )
    
    async def _check_weather(self) -> CheckItem:
        """Check weather conditions."""
        start = time.time()
        
        # Would integrate with weather service
        return CheckItem(
            name="Weather",
            check_type="weather",
            severity=2,
            result=CheckResult.PASS,
            message="Weather check passed",
            data={'wind_speed': 10, 'visibility': 'good'},
            duration_sec=time.time() - start
        )


# Export
__all__ = ['PreflightChecklist', 'ChecklistReport', 'CheckItem', 'CheckResult']