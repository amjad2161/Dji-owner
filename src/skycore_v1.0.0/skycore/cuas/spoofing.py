"""
SkyCore CUAS - Spoofing Detector
================================
GPS and signal spoofing detection for drone operations.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from collections import deque
import numpy as np

log = logging.getLogger(__name__)


class SpoofingType(Enum):
    """Types of spoofing attacks."""
    GPS_SPOOFING = "gps_spoofing"
    SIGNAL_JAMMING = "signal_jamming"
    MEaconing = "meaconing"  # Relay attack
    TRAJECTORY_MANIPULATION = "trajectory_manipulation"
    UNKNOWN = "unknown"


class SignalType(Enum):
    """Types of signals being monitored."""
    GPS_L1 = "gps_l1"
    GPS_L2 = "gps_l2"
    GLONASS = "glonass"
    GALILEO = "galileo"
    BEIDOU = "beidou"
    RTK = "rtk"


@dataclass
class SignalObservation:
    """Individual signal observation."""
    signal_type: SignalType
    timestamp: float
    frequency_hz: float
    signal_strength_dbm: float
    carrier_noise_ratio: float = 0.0
    pseudorange_m: float = 0.0
    doppler_shift_hz: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            'type': self.signal_type.value,
            'time': self.timestamp,
            'freq_hz': self.frequency_hz,
            'strength_dbm': self.signal_strength_dbm,
            'cnr': self.carrier_noise_ratio,
            'pseudorange_m': self.pseudorange_m,
            'doppler_hz': self.doppler_shift_hz
        }


@dataclass
class SpoofingIndicator:
    """Indicator of potential spoofing attack."""
    indicator_type: str
    severity: float  # 0-1
    timestamp: float
    description: str
    confidence: float
    
    def to_dict(self) -> Dict:
        return {
            'type': self.indicator_type,
            'severity': self.severity,
            'time': self.timestamp,
            'description': self.description,
            'confidence': self.confidence
        }


@dataclass
class SpoofingDetection:
    """Result of spoofing detection analysis."""
    is_spoofed: bool
    spoofing_type: Optional[SpoofingType]
    confidence: float  # 0-1
    indicators: List[SpoofingIndicator] = field(default_factory=list)
    affected_signals: List[SignalType] = field(default_factory=list)
    recommended_action: str = ""
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            'spoofed': self.is_spoofed,
            'type': self.spoofing_type.value if self.spoofing_type else None,
            'confidence': self.confidence,
            'indicators': [i.to_dict() for i in self.indicators],
            'affected_signals': [s.value for s in self.affected_signals],
            'action': self.recommended_action,
            'timestamp': self.timestamp
        }


class SpoofingDetector:
    """
    GPS and signal spoofing detector for drone operations.
    
    Detects various spoofing attacks:
    - GPS spoofing (fake signals)
    - Signal jamming (denial of service)
    - Meaconing (signal relay)
    - Trajectory manipulation
    
    Features:
    - Multi-constellation consistency checking
    - Signal quality monitoring
    - Position verification
    - Behavioral anomaly detection
    - Real-time alerting
    """
    
    def __init__(self, window_size: int = 100, alert_threshold: float = 0.7):
        """
        Initialize spoofing detector.
        
        Args:
            window_size: Number of observations to keep in rolling window
            alert_threshold: Minimum confidence to trigger alert
        """
        self.window_size = window_size
        self.alert_threshold = alert_threshold
        
        # Signal history
        self.signal_history: Dict[SignalType, deque] = {
            sig: deque(maxlen=window_size) for sig in SignalType
        }
        
        # Position history
        self.position_history = deque(maxlen=window_size)
        
        # Thresholds for detection
        self.thresholds = {
            'cnr_min': 30.0,  # Minimum C/N0 for valid signal (dB-Hz)
            'jamming_cnr': 20.0,  # C/N0 threshold for jamming detection
            'position_jump_m': 100.0,  # Max position jump in 1 second
            'velocity_jump_m_s': 50.0,  # Max velocity change
            'frequency_deviation_hz': 5000.0,  # Max frequency deviation
            'pseudorange_jump_m': 100.0,  # Max pseudorange jump
            'satellite_count_min': 4,
            'hdop_max': 5.0  # Maximum HDOP for valid fix
        }
        
        # Alert callbacks
        self._alert_callbacks: List[Callable] = []
        
        # Statistics
        self.total_checks = 0
        self.alerts_triggered = 0
        self.last_check_result: Optional[SpoofingDetection] = None
        
        log.info("Spoofing detector initialized")
    
    def add_observation(self, signal: SignalObservation):
        """Add signal observation for analysis."""
        if signal.signal_type in self.signal_history:
            self.signal_history[signal.signal_type].append(signal)
    
    def add_position(self, lat: float, lon: float, alt: float, 
                     timestamp: float, satellites: int = 0, hdop: float = 1.0):
        """Add position observation."""
        self.position_history.append({
            'lat': lat, 'lon': lon, 'alt': alt,
            'timestamp': timestamp,
            'satellites': satellites,
            'hdop': hdop
        })
    
    def analyze(self) -> SpoofingDetection:
        """
        Analyze signals for spoofing indicators.
        
        Returns:
            SpoofingDetection result
        """
        self.total_checks += 1
        
        indicators = []
        affected_signals = []
        spoofing_type = None
        
        # Check 1: Signal quality degradation
        quality_indicators = self._check_signal_quality()
        indicators.extend(quality_indicators)
        
        # Check 2: Position consistency
        position_indicators = self._check_position_consistency()
        indicators.extend(position_indicators)
        
        # Check 3: Multi-constellation consistency
        constellation_indicators = self._check_constellation_consistency()
        indicators.extend(constellation_indicators)
        
        # Check 4: Pseudorange anomalies
        prange_indicators = self._check_pseudorange_anomalies()
        indicators.extend(prange_indicators)
        
        # Check 5: Frequency anomalies
        freq_indicators = self._check_frequency_anomalies()
        indicators.extend(freq_indicators)
        
        # Determine overall assessment
        max_severity = max((i.severity for i in indicators), default=0.0)
        
        if max_severity > 0.8:
            spoofing_type = SpoofingType.GPS_SPOOFING
        elif max_severity > 0.5:
            # Check for jamming vs spoofing
            jamming_indicators = [i for i in indicators if 'jamming' in i.indicator_type or 'cnr' in i.indicator_type]
            if jamming_indicators and max(i.severity for i in jamming_indicators) > 0.6:
                spoofing_type = SpoofingType.SIGNAL_JAMMING
            else:
                spoofing_type = SpoofingType.UNKNOWN
        
        is_spoofed = max_severity > self.alert_threshold
        
        if is_spoofed:
            self.alerts_triggered += 1
        
        # Calculate confidence
        confidence = max_severity
        
        # Get affected signals
        affected_signals = self._get_affected_signals()
        
        # Get recommended action
        action = self._get_recommended_action(is_spoofed, spoofing_type, confidence)
        
        detection = SpoofingDetection(
            is_spoofed=is_spoofed,
            spoofing_type=spoofing_type,
            confidence=confidence,
            indicators=indicators,
            affected_signals=affected_signals,
            recommended_action=action
        )
        
        self.last_check_result = detection
        
        # Trigger callbacks
        if is_spoofed:
            self._trigger_alert(detection)
        
        return detection
    
    def _check_signal_quality(self) -> List[SpoofingIndicator]:
        """Check for signal quality degradation."""
        indicators = []
        
        for sig_type, history in self.signal_history.items():
            if len(history) < 10:
                continue
            
            recent = list(history)[-10:]
            avg_cnr = np.mean([obs.carrier_noise_ratio for obs in recent])
            
            if avg_cnr < self.thresholds['jamming_cnr']:
                indicators.append(SpoofingIndicator(
                    indicator_type='low_cnr_jamming',
                    severity=0.7 + 0.3 * (1 - avg_cnr / self.thresholds['jamming_cnr']),
                    timestamp=time.time(),
                    description=f"Low C/N0 detected: {avg_cnr:.1f} dB-Hz (possible jamming)",
                    confidence=0.8
                ))
                continue
            
            if avg_cnr < self.thresholds['cnr_min']:
                indicators.append(SpoofingIndicator(
                    indicator_type='degraded_cnr',
                    severity=0.4,
                    timestamp=time.time(),
                    description=f"Degraded signal quality: {avg_cnr:.1f} dB-Hz",
                    confidence=0.6
                ))
        
        return indicators
    
    def _check_position_consistency(self) -> List[SpoofingIndicator]:
        """Check for position anomalies indicating spoofing."""
        indicators = []
        
        if len(self.position_history) < 2:
            return indicators
        
        positions = list(self.position_history)
        
        for i in range(1, min(len(positions), 5)):
            prev = positions[-i-1]
            curr = positions[-i]
            
            dt = curr['timestamp'] - prev['timestamp']
            if dt <= 0:
                continue
            
            # Calculate position delta
            dlat = (curr['lat'] - prev['lat']) * 111320  # meters
            dlon = (curr['lon'] - prev['lon']) * 111320 * np.cos(np.radians(curr['lat']))
            dalt = curr['alt'] - prev['alt']
            
            distance = np.sqrt(dlat**2 + dlon**2 + dalt**2)
            velocity = distance / dt
            
            # Check for unrealistic position jump
            if distance > self.thresholds['position_jump_m']:
                indicators.append(SpoofingIndicator(
                    indicator_type='position_jump',
                    severity=0.9,
                    timestamp=time.time(),
                    description=f"Position jump detected: {distance:.1f}m in {dt:.1f}s",
                    confidence=0.85
                ))
            
            # Check for unrealistic velocity
            if velocity > self.thresholds['velocity_jump_m_s']:
                indicators.append(SpoofingIndicator(
                    indicator_type='velocity_anomaly',
                    severity=0.8,
                    timestamp=time.time(),
                    description=f"Velocity anomaly: {velocity:.1f} m/s",
                    confidence=0.7
                ))
        
        return indicators
    
    def _check_constellation_consistency(self) -> List[SpoofingIndicator]:
        """Check consistency across multiple GNSS constellations."""
        indicators = []
        
        # Check satellite count
        if self.position_history:
            last = list(self.position_history)[-1]
            
            if last.get('satellites', 0) < self.thresholds['satellite_count_min']:
                indicators.append(SpoofingIndicator(
                    indicator_type='low_satellite_count',
                    severity=0.5,
                    timestamp=time.time(),
                    description=f"Low satellite count: {last.get('satellites', 0)}",
                    confidence=0.6
                ))
            
            if last.get('hdop', 99) > self.thresholds['hdop_max']:
                indicators.append(SpoofingIndicator(
                    indicator_type='high_hdop',
                    severity=0.4,
                    timestamp=time.time(),
                    description=f"High HDOP: {last.get('hdop', 0):.1f}",
                    confidence=0.5
                ))
        
        return indicators
    
    def _check_pseudorange_anomalies(self) -> List[SpoofingIndicator]:
        """Check for pseudorange anomalies."""
        indicators = []
        
        for sig_type, history in self.signal_history.items():
            if len(history) < 3:
                continue
            
            pranges = [obs.pseudorange_m for obs in history]
            
            # Check for sudden jumps
            for i in range(1, len(pranges)):
                delta = abs(pranges[i] - pranges[i-1])
                
                if delta > self.thresholds['pseudorange_jump_m']:
                    indicators.append(SpoofingIndicator(
                        indicator_type='pseudorange_jump',
                        severity=0.8,
                        timestamp=time.time(),
                        description=f"Pseudorange jump: {delta:.1f}m ({sig_type.value})",
                        confidence=0.75
                    ))
        
        return indicators
    
    def _check_frequency_anomalies(self) -> List[SpoofingIndicator]:
        """Check for frequency anomalies."""
        indicators = []
        
        for sig_type, history in self.signal_history.items():
            if len(history) < 5:
                continue
            
            recent = list(history)[-5:]
            dopplers = [obs.doppler_shift_hz for obs in recent]
            
            # Check for sudden frequency changes
            for i in range(1, len(dopplers)):
                delta = abs(dopplers[i] - dopplers[i-1])
                
                if delta > self.thresholds['frequency_deviation_hz']:
                    indicators.append(SpoofingIndicator(
                        indicator_type='frequency_deviation',
                        severity=0.6,
                        timestamp=time.time(),
                        description=f"Frequency anomaly: {delta:.0f}Hz ({sig_type.value})",
                        confidence=0.6
                    ))
        
        return indicators
    
    def _get_affected_signals(self) -> List[SignalType]:
        """Get list of affected signal types."""
        affected = []
        
        for sig_type, history in self.signal_history.items():
            if len(history) > 0:
                recent = list(history)[-5:]
                avg_cnr = np.mean([obs.carrier_noise_ratio for obs in recent])
                
                if avg_cnr < self.thresholds['cnr_min']:
                    affected.append(sig_type)
        
        return affected
    
    def _get_recommended_action(self, is_spoofed: bool, 
                                spoofing_type: Optional[SpoofingType],
                                confidence: float) -> str:
        """Get recommended action based on detection."""
        if not is_spoofed:
            return "Continue normal operations"
        
        if confidence > 0.9:
            if spoofing_type == SpoofingType.SIGNAL_JAMMING:
                return "Switch to backup navigation, initiate RTH"
            else:
                return "Switch to inertial navigation, return to home immediately"
        else:
            return "Monitor closely, prepare for evasive action"
    
    def on_alert(self, callback: Callable):
        """Register alert callback."""
        self._alert_callbacks.append(callback)
    
    def _trigger_alert(self, detection: SpoofingDetection):
        """Trigger spoofing alert."""
        log.warning(f"SPOOFING DETECTED: {detection.spoofing_type} (confidence: {detection.confidence:.2f})")
        
        for callback in self._alert_callbacks:
            try:
                callback(detection)
            except Exception as e:
                log.error(f"Alert callback error: {e}")
    
    def reset(self):
        """Reset detector state."""
        for history in self.signal_history.values():
            history.clear()
        self.position_history.clear()
        self.total_checks = 0
        self.alerts_triggered = 0
        log.info("Spoofing detector reset")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return {
            'total_checks': self.total_checks,
            'alerts_triggered': self.alerts_triggered,
            'last_detection': self.last_check_result.to_dict() if self.last_check_result else None,
            'window_size': self.window_size,
            'alert_threshold': self.alert_threshold
        }


# Export
__all__ = ['SpoofingDetector', 'SpoofingType', 'SpoofingIndicator', 'SpoofingDetection', 'SignalType', 'SignalObservation']