"""C-UAS (Counter-Unmanned Aircraft System) detection module.

Implements:
- Drone detection via multiple sensors
- RF signal analysis
- Acoustic detection
- Radar detection
- Multi-sensor fusion for tracking

Note: Detection only, no attack capabilities (legal compliance).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
import numpy as np
from numpy.typing import NDArray
import time


@dataclass
class CUAConfig:
    """C-UAS configuration."""
    # Detection methods
    enable_rf: bool = True
    enable_acoustic: bool = True
    enable_radar: bool = False
    enable_camera: bool = True
    
    # Detection parameters
    detection_range: float = 500.0    # meters
    max_tracked: int = 50
    track_timeout: float = 10.0        # seconds
    
    # Fusion
    fusion_mode: str = "probabilistic"  # "simple", "kalman", "probabilistic"
    
    # Alert thresholds
    alert_confidence: float = 0.7
    track_min_hits: int = 3


@dataclass
class Detection:
    """Single detection."""
    timestamp: float
    sensor_type: str        # "rf", "acoustic", "radar", "camera"
    position: NDArray       # [x, y, z] in NED
    velocity: NDArray       # [vx, vy, vz]
    confidence: float      # 0-1
    features: Dict         # Sensor-specific features


@dataclass
class Track:
    """Tracked object."""
    track_id: int
    position: NDArray      # Current position
    velocity: NDArray       # Current velocity
    last_update: float
    
    # History
    positions: List[NDArray] = field(default_factory=list)
    detections: List[Detection] = field(default_factory=list)
    
    # Statistics
    hit_count: int = 0
    miss_count: int = 0
    average_confidence: float = 0.0
    
    # Classification
    classification: str = "unknown"
    classification_confidence: float = 0.0
    
    # Alert state
    alerted: bool = False
    alert_time: Optional[float] = None


class RFCrossCorrelation:
    """RF signal cross-correlation for drone detection."""
    
    def __init__(self, config: Optional[CUAConfig] = None):
        self.config = config or CUAConfig()
        
        # Known drone frequencies
        self.drone_frequencies = [
            2400,  # 2.4GHz WiFi
            5100,  # 5.8GHz
            900,   # 900MHz
        ]
        
        self.signal_threshold = -80  # dBm
        self.min_correlation = 0.3
    
    def analyze_signal(
        self,
        signal_strength: float,
        frequency: float,
        signal_pattern: NDArray
    ) -> Tuple[bool, float, Dict]:
        """Analyze RF signal for drone signature.
        
        Args:
            signal_strength: Signal strength in dBm
            frequency: Frequency in MHz
            signal_pattern: Time-series signal data
            
        Returns:
            (is_drone, confidence, features)
        """
        features = {}
        
        # Check if in drone frequency band
        is_drone_band = any(abs(frequency - f) < 50 for f in self.drone_frequencies)
        features['drone_band'] = is_drone_band
        
        # Signal strength analysis
        features['strength'] = signal_strength
        features['is_strong'] = signal_strength > self.signal_threshold
        
        # Pattern analysis (simplified)
        # Real implementation would use matched filters, cyclostationary analysis
        pattern_std = np.std(signal_pattern)
        features['pattern_std'] = pattern_std
        
        # Hopping detection (drones often hop frequencies)
        # Simplified: check variance in frequency measurement
        freq_variance = np.var([frequency])  # Would need history
        
        # Compute confidence
        confidence = 0.0
        
        if is_drone_band and signal_strength > self.signal_threshold:
            confidence += 0.3
        
        if pattern_std > 5:  # Modulated signal
            confidence += 0.3
        
        if freq_variance > 0:  # Hopping detected
            confidence += 0.2
        
        confidence = min(confidence, 1.0)
        
        return confidence > 0.3, confidence, features
    
    def estimate_direction(
        self,
        signal_strengths: List[float],
        antenna_gains: List[float]
    ) -> Optional[NDArray]:
        """Estimate signal direction from multiple antennas.
        
        Args:
            signal_strengths: Signal strength at each antenna
            antenna_gains: Antenna gain patterns
            
        Returns:
            Direction vector or None
        """
        if len(signal_strengths) < 2:
            return None
        
        # Simple amplitude comparison
        # Real implementation would use DoA algorithms (MUSIC, beamforming)
        
        strengths = np.array(signal_strengths)
        max_idx = np.argmax(strengths)
        
        # Direction based on antenna positions
        # Simplified: assume antennas at known positions
        directions = [
            np.array([1, 0, 0]),   # East
            np.array([-1, 0, 0]),  # West
            np.array([0, 1, 0]),   # North
            np.array([0, -1, 0]),  # South
        ]
        
        if max_idx < len(directions):
            return directions[max_idx]
        
        return None


class AcousticDetector:
    """Acoustic detection using microphone arrays."""
    
    def __init__(self, config: Optional[CUAConfig] = None):
        self.config = config or CUAConfig()
        
        # Microphone positions
        self.mic_positions = [
            np.array([0, 0, 0]),
            np.array([0.1, 0, 0]),
            np.array([0, 0.1, 0]),
            np.array([0.1, 0.1, 0]),
        ]
        
        # Known drone sounds (simplified)
        self.drone_frequencies = [85, 150, 200, 400]  # Hz (motor RPM harmonics)
        
        # Noise floor
        self.noise_floor = -60  # dB
    
    def analyze_audio(
        self,
        audio_data: NDArray,
        sample_rate: float
    ) -> Tuple[bool, float, Dict]:
        """Analyze audio for drone sound.
        
        Args:
            audio_data: Audio samples (N x num_mics)
            sample_rate: Sample rate in Hz
            
        Returns:
            (is_drone, confidence, features)
        """
        features = {}
        
        # Compute FFT for spectrum analysis
        n = len(audio_data)
        spectrum = np.abs(np.fft.rfft(audio_data[:, 0]))  # First mic
        
        freq_axis = np.fft.rfftfreq(n, 1 / sample_rate)
        
        # Find peaks in expected drone frequency range (80-500 Hz)
        drone_range = (freq_axis > 80) & (freq_axis < 500)
        drone_spectrum = spectrum[drone_range]
        
        # Check for characteristic peaks
        peak_threshold = np.max(drone_spectrum) * 0.3
        peaks = drone_spectrum > peak_threshold
        
        features['num_peaks'] = np.sum(peaks)
        features['peak_freqs'] = freq_axis[drone_range][peaks].tolist()
        
        # Motor harmonic detection
        # Drones have harmonically related peaks
        harmonic_score = 0.0
        for base_freq in self.drone_frequencies:
            for harmonic in range(1, 5):
                target_freq = base_freq * harmonic
                
                # Check if peak exists at harmonic
                freq_idx = np.argmin(np.abs(freq_axis - target_freq))
                
                if freq_idx < len(spectrum):
                    peak_power = spectrum[freq_idx]
                    if peak_power > self.noise_floor:
                        harmonic_score += 0.1
        
        features['harmonic_score'] = harmonic_score
        
        # Compute confidence
        confidence = 0.0
        
        if features['num_peaks'] > 2:
            confidence += 0.3
        
        if harmonic_score > 0.3:
            confidence += 0.5
        
        confidence = min(confidence, 1.0)
        
        return confidence > 0.4, confidence, features
    
    def estimate_direction(
        self,
        audio_data: NDArray,
        sample_rate: float
    ) -> Optional[NDArray]:
        """Estimate direction using TDOA (Time Difference of Arrival).
        
        Args:
            audio_data: Audio samples from microphone array
            sample_rate: Sample rate
            
        Returns:
            Direction vector or None
        """
        # Simplified TDOA using cross-correlation
        ref_signal = audio_data[:, 0]  # Reference microphone
        
        delays = []
        for i in range(1, len(self.mic_positions)):
            mic_signal = audio_data[:, i]
            
            # Cross-correlation
            correlation = np.correlate(ref_signal, mic_signal, mode='full')
            delay_idx = np.argmax(correlation) - len(ref_signal) // 2
            
            delay = delay_idx / sample_rate
            delays.append(delay)
        
        # Estimate DoA from delays
        # Simplified: use first two microphones
        if len(delays) >= 1:
            c = 343  # Speed of sound m/s
            d = 0.1  # Microphone spacing
            
            # Simplified angle estimate
            angle = np.arcsin(np.clip(delays[0] * c / d, -1, 1))
            
            return np.array([np.cos(angle), np.sin(angle), 0])
        
        return None


class MultiSensorFusion:
    """Fuse detections from multiple sensors."""
    
    def __init__(self, config: Optional[CUAConfig] = None):
        self.config = config or CUAConfig()
        
        # Kalman filter state for each track
        self.tracks: Dict[int, Track] = {}
        self.next_track_id = 1
        
        # Sensor covariances
        self.sensor_covariances = {
            'rf': 50.0,      # meters²
            'acoustic': 100.0,
            'radar': 10.0,
            'camera': 25.0,
        }
        
        # Track management
        self.track_timeout = config.track_timeout if config else 10.0
    
    def add_detection(self, detection: Detection) -> Optional[int]:
        """Add detection to fusion.
        
        Args:
            detection: Single detection
            
        Returns:
            Track ID if associated, None if new track
        """
        # Try to associate with existing track
        associated_track = None
        
        for track_id, track in self.tracks.items():
            # Simple association: distance and time check
            dist = np.linalg.norm(detection.position - track.position)
            dt = detection.timestamp - track.last_update
            
            if dist < 20 and dt < 2.0:  # 20m, 2s threshold
                associated_track = track_id
                break
        
        if associated_track is not None:
            # Update existing track
            return self._update_track(associated_track, detection)
        else:
            # Create new track
            return self._create_track(detection)
    
    def _create_track(self, detection: Detection) -> int:
        """Create new track from detection."""
        track_id = self.next_track_id
        self.next_track_id += 1
        
        track = Track(
            track_id=track_id,
            position=detection.position,
            velocity=detection.velocity,
            last_update=detection.timestamp,
            positions=[detection.position.copy()],
            detections=[detection],
            hit_count=1,
            average_confidence=detection.confidence
        )
        
        self.tracks[track_id] = track
        
        return track_id
    
    def _update_track(self, track_id: int, detection: Detection) -> int:
        """Update existing track with new detection."""
        track = self.tracks[track_id]
        
        # Simple Kalman-like update
        alpha = 0.5  # Smoothing factor
        
        # Update position
        track.position = alpha * detection.position + (1 - alpha) * track.position
        
        # Update velocity
        dt = detection.timestamp - track.last_update
        if dt > 0:
            track.velocity = (detection.position - track.positions[-1]) / dt
        
        track.last_update = detection.timestamp
        track.positions.append(detection.position.copy())
        track.detections.append(detection)
        
        # Update statistics
        track.hit_count += 1
        track.average_confidence = (
            track.average_confidence * (track.hit_count - 1) + detection.confidence
        ) / track.hit_count
        
        # Limit history
        if len(track.positions) > 100:
            track.positions.pop(0)
        
        return track_id
    
    def prune_tracks(self, current_time: float) -> List[int]:
        """Remove stale tracks.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            List of removed track IDs
        """
        removed = []
        
        for track_id in list(self.tracks.keys()):
            track = self.tracks[track_id]
            
            if current_time - track.last_update > self.track_timeout:
                del self.tracks[track_id]
                removed.append(track_id)
        
        return removed
    
    def classify_tracks(self) -> None:
        """Classify tracks as drone or non-drone."""
        for track in self.tracks.values():
            if track.hit_count >= self.config.track_min_hits:
                # Classify based on features
                features = self._extract_features(track)
                
                # Simple rule-based classification
                is_drone = self._is_likely_drone(features)
                
                if is_drone:
                    track.classification = "drone"
                    track.classification_confidence = track.average_confidence
                    
                    if track.classification_confidence > self.config.alert_confidence:
                        track.alerted = True
                        track.alert_time = time.time()
                else:
                    track.classification = "unknown"
    
    def _extract_features(self, track: Track) -> Dict:
        """Extract features for classification."""
        if len(track.positions) < 2:
            return {}
        
        positions = np.array(track.positions)
        
        # Movement characteristics
        mean_velocity = np.mean(np.diff(positions, axis=0), axis=0)
        velocity_std = np.std(np.diff(positions, axis=0), axis=0)
        
        features = {
            'mean_speed': np.linalg.norm(mean_velocity),
            'speed_variance': np.linalg.norm(velocity_std),
            'altitude': track.position[2] if len(track.position) > 2 else 0,
            'num_hits': track.hit_count,
            'avg_confidence': track.average_confidence,
        }
        
        return features
    
    def _is_likely_drone(self, features: Dict) -> bool:
        """Determine if track is likely a drone."""
        # Rules:
        # - Speed between 0 and 30 m/s (typical drone)
        # - Not too variable (balloons drift, birds vary more)
        # - Altitude reasonable (not too high)
        
        if features.get('mean_speed', 0) > 35:
            return False
        
        if features.get('speed_variance', 0) > 10:
            return False
        
        if features.get('altitude', 0) > 400:
            return False
        
        if features.get('avg_confidence', 0) < 0.4:
            return False
        
        return True
    
    def get_tracks(self) -> List[Track]:
        """Get all current tracks."""
        return list(self.tracks.values())
    
    def get_alerts(self) -> List[Track]:
        """Get all tracks that have alerted."""
        return [t for t in self.tracks.values() if t.alerted]


class CUASSystem:
    """Complete C-UAS detection system."""
    
    def __init__(self, config: Optional[CUAConfig] = None):
        self.config = config or CUAConfig()
        
        # Sensors
        self.rf_detector = RFCrossCorrelation(config)
        self.acoustic_detector = AcousticDetector(config)
        
        # Fusion
        self.fusion = MultiSensorFusion(config)
        
        # Callbacks
        self.on_alert: Optional[callable] = None
    
    def process_rf_detection(
        self,
        signal_strength: float,
        frequency: float,
        signal_pattern: NDArray
    ) -> Optional[Detection]:
        """Process RF detection."""
        is_drone, confidence, features = self.rf_detector.analyze_signal(
            signal_strength, frequency, signal_pattern
        )
        
        if not is_drone:
            return None
        
        direction = self.rf_detector.estimate_direction([signal_strength], [1.0])
        
        if direction is None:
            direction = np.zeros(3)
        
        # Estimate range (simplified)
        range_est = 100 * (1 - confidence) + 20
        
        position = direction * range_est
        position[2] = 30  # Assume altitude
        
        return Detection(
            timestamp=time.time(),
            sensor_type='rf',
            position=position,
            velocity=np.zeros(3),
            confidence=confidence,
            features=features
        )
    
    def process_acoustic_detection(
        self,
        audio_data: NDArray,
        sample_rate: float
    ) -> Optional[Detection]:
        """Process acoustic detection."""
        is_drone, confidence, features = self.acoustic_detector.analyze_audio(
            audio_data, sample_rate
        )
        
        if not is_drone:
            return None
        
        direction = self.acoustic_detector.estimate_direction(audio_data, sample_rate)
        
        if direction is None:
            direction = np.zeros(3)
        
        range_est = 50 * (1 - confidence) + 10
        
        position = direction * range_est
        position[2] = 30
        
        return Detection(
            timestamp=time.time(),
            sensor_type='acoustic',
            position=position,
            velocity=np.zeros(3),
            confidence=confidence,
            features=features
        )
    
    def update(self) -> List[Track]:
        """Update C-UAS system, return current tracks."""
        current_time = time.time()
        
        # Prune stale tracks
        self.fusion.prune_tracks(current_time)
        
        # Classify tracks
        self.fusion.classify_tracks()
        
        # Get alerts
        alerts = self.fusion.get_alerts()
        
        if alerts and self.on_alert:
            for alert in alerts:
                self.on_alert(alert)
        
        return self.fusion.get_tracks()


def demo_cuas():
    """Demonstrate C-UAS detection."""
    print("=" * 60)
    print("C-UAS Detection Demo")
    print("=" * 60)
    
    # Create C-UAS system
    config = CUAConfig()
    cuas = CUASSystem(config)
    
    # Alert callback
    def on_alert(track):
        print(f"  ALERT: Drone detected at ({track.position[0]:.1f}, {track.position[1]:.1f}, {track.position[2]:.1f})m")
    
    cuas.on_alert = on_alert
    
    # Simulate RF detection
    print("\nSimulating RF detection...")
    
    signal_pattern = np.random.randn(1000) + np.sin(np.arange(1000) * 0.1) * 5
    
    detection = cuas.process_rf_detection(
        signal_strength=-70,  # dBm
        frequency=2400,        # MHz
        signal_pattern=signal_pattern
    )
    
    if detection:
        print(f"  Detection: pos=({detection.position[0]:.1f}, {detection.position[1]:.1f})m, "
              f"conf={detection.confidence:.2f}")
        cuas.fusion.add_detection(detection)
    
    # Simulate acoustic detection
    print("\nSimulating acoustic detection...")
    
    audio = np.random.randn(1000, 4)
    audio[:, 0] += np.sin(2 * np.pi * 150 * np.arange(1000) / 48000)  # 150 Hz drone sound
    
    detection = cuas.process_acoustic_detection(audio, 48000)
    
    if detection:
        print(f"  Detection: pos=({detection.position[0]:.1f}, {detection.position[1]:.1f})m, "
              f"conf={detection.confidence:.2f}")
        cuas.fusion.add_detection(detection)
    
    # Update system
    print("\n" + "=" * 40)
    print("System Update")
    print("=" * 40)
    
    tracks = cuas.update()
    print(f"  Active tracks: {len(tracks)}")
    
    for track in tracks:
        print(f"  Track {track.track_id}: {track.classification}, "
              f"pos=({track.position[0]:.1f}, {track.position[1]:.1f})m, "
              f"conf={track.average_confidence:.2f}")
    
    # Simulate multiple detections
    print("\n" + "=" * 40)
    print("Simulating Multiple Detections")
    print("=" * 40)
    
    for i in range(5):
        detection = Detection(
            timestamp=time.time(),
            sensor_type='rf',
            position=np.array([50 + i * 10, 30 + i * 5, 40]),
            velocity=np.array([5, 2, 0]),
            confidence=0.8,
            features={}
        )
        cuas.fusion.add_detection(detection)
    
    tracks = cuas.update()
    print(f"  Tracks after updates: {len(tracks)}")
    
    alerts = cuas.fusion.get_alerts()
    print(f"  Active alerts: {len(alerts)}")


if __name__ == "__main__":
    demo_cuas()