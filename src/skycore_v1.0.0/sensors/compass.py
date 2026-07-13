"""Magnetometer/compass sensor for heading estimation.

Implements:
- Earth's magnetic field model
- Magnetometer calibration (hard/soft iron)
- Heading computation with tilt compensation
- Magnetic declination adjustment
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
import numpy as np
from numpy.typing import NDArray
import time


@dataclass
class CompassConfig:
    """Magnetometer configuration."""
    model: str = "generic"
    
    # Earth's magnetic field (expected magnitude)
    reference_field: float = 45.0  # μT (microTesla)
    
    # Calibration
    hard_iron: NDArray = field(default_factory=lambda: np.zeros(3))
    soft_iron: NDArray = field(default_factory=lambda: np.eye(3))
    
    # Magnetic declination (degrees, positive = East)
    declination: float = 0.0
    
    # Noise parameters
    noise_std: float = 0.01  # μT
    heading_noise_std: float = 1.0  # degrees
    
    # Update rate
    update_rate: float = 100.0  # Hz
    
    # Disturbance detection
    disturbance_threshold: float = 20.0  # μT deviation


@dataclass
class CompassReading:
    """Magnetometer reading."""
    timestamp: float
    magnetic_field: NDArray  # μT in body frame (x, y, z)
    
    # Computed values
    heading: float = 0.0       # degrees (0-360, North = 0)
    pitch: float = 0.0        # degrees
    roll: float = 0.0         # degrees
    
    # Quality
    quality: float = 1.0      # 0-1 quality indicator
    disturbance: bool = False


class MagneticFieldModel:
    """World Magnetic Model (simplified)."""
    
    # IGRF-14 coefficients (simplified, valid ~2020-2025)
    # These are approximate for demo purposes
    IGRF_COEFFICIENTS = {
        # Main field coefficients (n, m, g_nm, h_nm)
        'g10': -29404.5,
        'g11': -1450.9,
        'g20': -2499.6,
        'g21': 2982.0,
        'g22': 1676.8,
        'h21': -2991.5,
        'h22': -734.8,
    }
    
    def __init__(self, latitude: float = 32.0, longitude: float = 35.0, altitude: float = 0.0):
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        
        # Compute reference field at this location
        self._compute_reference()
    
    def _compute_reference(self) -> None:
        """Compute expected magnetic field vector at location."""
        lat_rad = np.radians(self.latitude)
        lon_rad = np.radians(self.longitude)
        
        # Simplified field computation
        # Real WMM uses spherical harmonic expansion
        
        # Horizontal intensity (approximate)
        H = self.IGRF_COEFFICIENTS.get('g10', -29404.5) * np.cos(lat_rad) + \
            self.IGRF_COEFFICIENTS.get('g11', -1450.9) * np.sin(lat_rad) * np.cos(lon_rad)
        
        # Vertical component
        Z = self.IGRF_COEFFICIENTS.get('g10', -29404.5) * np.sin(lat_rad) - \
            self.IGRF_COEFFICIENTS.get('g11', -1450.9) * np.cos(lat_rad) * np.cos(lon_rad)
        
        # Horizontal components
        X = H * np.sin(lon_rad)
        Y = H * np.cos(lon_rad)
        
        self.field_vector = np.array([X, Y, Z]) / 1000  # Convert to mT, then normalize for simulation
        self.field_magnitude = np.linalg.norm(self.field_vector)
        
        # Declination (simplified)
        self.declination = np.degrees(np.arctan2(Y, X))
    
    def get_field(self) -> NDArray:
        """Get expected field vector at location."""
        return self.field_vector.copy()
    
    def get_magnitude(self) -> float:
        """Get expected field magnitude."""
        return self.field_magnitude
    
    def get_declination(self) -> float:
        """Get magnetic declination in degrees."""
        return self.declination


class MagnetometerCalibrator:
    """Magnetometer calibration (hard/soft iron compensation)."""
    
    def __init__(self):
        self.samples: List[NDArray] = []
        self.max_samples = 1000
        
        # Calibration parameters
        self.hard_iron = np.zeros(3)
        self.soft_iron = np.eye(3)
        
        self.calibrated = False
    
    def add_sample(self, measurement: NDArray) -> None:
        """Add measurement sample for calibration."""
        self.samples.append(measurement.copy())
        
        if len(self.samples) > self.max_samples:
            self.samples.pop(0)
    
    def calibrate(self) -> Tuple[NDArray, NDArray]:
        """Calibrate magnetometer using ellipsoid fitting.
        
        Returns:
            (hard_iron, soft_iron)
        """
        if len(self.samples) < 100:
            print(f"Not enough samples: {len(self.samples)} < 100")
            return self.hard_iron, self.soft_iron
        
        samples = np.array(self.samples)
        
        # Fit ellipsoid to data
        # The equation is: (x - h)^T A (x - h) = 1
        # where h is hard iron and A encodes soft iron + scale
        
        # Use least squares to fit ellipsoid
        # Expand to quadratic form: x^T B x + c^T x + d = 0
        
        n = len(samples)
        
        # Build design matrix
        D = np.zeros((n, 10))
        for i, s in enumerate(samples):
            x, y, z = s
            D[i] = [
                x*x, y*y, z*z,
                2*x*y, 2*x*z, 2*y*z,
                2*x, 2*y, 2*z, 1
            ]
        
        # Solve for coefficients
        # Using SVD for numerical stability
        U, S, Vt = np.linalg.svd(D, full_matrices=True)
        coeffs = Vt[-1]  # Last singular vector
        
        # Build quadratic form matrix
        A = np.array([
            [coeffs[0], coeffs[3], coeffs[4]],
            [coeffs[3], coeffs[1], coeffs[5]],
            [coeffs[4], coeffs[5], coeffs[2]]
        ])
        
        B = np.array([coeffs[6], coeffs[7], coeffs[8]])
        d = coeffs[9]
        
        # Solve for center (hard iron)
        self.hard_iron = -np.linalg.inv(A) @ B / 2
        
        # Normalize to get soft iron matrix
        # First, translate samples
        centered = samples - self.hard_iron
        
        # Compute covariance
        cov = np.cov(centered.T)
        
        # Eigendecomposition to find ellipse axes
        eigenvalues, eigenvectors = np.linalg.eig(cov)
        
        # Average radius
        avg_radius = np.mean(np.sqrt(eigenvalues))
        
        # Soft iron correction
        self.soft_iron = eigenvectors @ np.diag(1 / np.sqrt(eigenvalues)) @ eigenvectors.T * avg_radius
        
        self.calibrated = True
        
        print(f"Calibration complete: {len(self.samples)} samples")
        print(f"  Hard iron: {self.hard_iron}")
        print(f"  Soft iron diagonal: {np.diag(self.soft_iron)}")
        
        return self.hard_iron, self.soft_iron
    
    def correct(self, measurement: NDArray) -> NDArray:
        """Apply calibration correction."""
        if not self.calibrated:
            return measurement
        
        # Hard iron subtraction
        corrected = measurement - self.hard_iron
        
        # Soft iron correction
        corrected = self.soft_iron @ corrected
        
        return corrected
    
    def reset(self) -> None:
        """Reset calibration."""
        self.samples = []
        self.hard_iron = np.zeros(3)
        self.soft_iron = np.eye(3)
        self.calibrated = False


class TiltCompensatedHeading:
    """Compute heading with tilt compensation using accelerometer."""
    
    def __init__(self, config: Optional[CompassConfig] = None):
        self.config = config or CompassConfig()
        
        # Pitch and roll angles from accelerometer
        self.pitch = 0.0
        self.roll = 0.0
        
        # Low-pass filter for angles
        self.filter_alpha = 0.1
    
    def update_attitude(self, accel: NDArray) -> None:
        """Update pitch and roll from accelerometer.
        
        Args:
            accel: Acceleration vector (m/s²)
        """
        # Normalize
        accel_norm = np.linalg.norm(accel)
        
        if accel_norm < 0.1:
            return
        
        accel_unit = accel / accel_norm
        
        # Compute angles (assuming approximately level)
        # pitch = atan2(-accel_x, sqrt(accel_y² + accel_z²))
        # roll = atan2(accel_y, accel_z)
        
        # Low-pass filter
        pitch_new = np.degrees(np.arctan2(-accel_unit[0], np.sqrt(accel_unit[1]**2 + accel_unit[2]**2)))
        roll_new = np.degrees(np.arctan2(accel_unit[1], accel_unit[2]))
        
        self.pitch = self.filter_alpha * pitch_new + (1 - self.filter_alpha) * self.pitch
        self.roll = self.filter_alpha * roll_new + (1 - self.filter_alpha) * self.roll
    
    def compute_heading(
        self,
        mag: NDArray,
        pitch: Optional[float] = None,
        roll: Optional[float] = None
    ) -> float:
        """Compute tilt-compensated heading.
        
        Args:
            mag: Magnetometer reading (body frame)
            pitch: Pitch angle in degrees (optional, uses internal)
            roll: Roll angle in degrees (optional, uses internal)
            
        Returns:
            Heading in degrees (0-360, North = 0)
        """
        if pitch is None:
            pitch = self.pitch
        if roll is None:
            roll = self.roll
        
        # Convert angles to radians
        pitch_rad = np.radians(pitch)
        roll_rad = np.radians(roll)
        
        # Tilt compensation matrix
        # Rotate magnetometer reading to horizontal frame
        
        # First, rotate about X axis (roll)
        cos_r = np.cos(roll_rad)
        sin_r = np.sin(roll_rad)
        
        mag_x_rot = mag[0]
        mag_y_rot = cos_r * mag[1] - sin_r * mag[2]
        mag_z_rot = sin_r * mag[1] + cos_r * mag[2]
        
        # Then, rotate about Y axis (pitch)
        cos_p = np.cos(pitch_rad)
        sin_p = np.sin(pitch_rad)
        
        mag_x_comp = cos_p * mag_x_rot + sin_p * mag_z_rot
        mag_y_comp = mag_y_rot
        # mag_z_comp = -sin_p * mag_x_rot + cos_p * mag_z_rot (not needed for heading)
        
        # Compute heading
        heading_rad = np.arctan2(mag_y_comp, mag_x_comp)
        heading_deg = np.degrees(heading_rad)
        
        # Normalize to 0-360
        heading_deg = (heading_deg + 360) % 360
        
        return heading_deg


class DisturbanceDetector:
    """Detect magnetic disturbances."""
    
    def __init__(self, config: Optional[CompassConfig] = None):
        self.config = config or CompassConfig()
        
        self.reference_magnitude = config.reference_field if config else 45.0
        self.threshold = config.disturbance_threshold if config else 20.0
        
        # Moving average for magnitude
        self.magnitude_history: List[float] = []
        self.max_history = 100
    
    def check_disturbance(self, field_magnitude: float) -> bool:
        """Check if magnetic field is disturbed.
        
        Args:
            field_magnitude: Current field magnitude
            
        Returns:
            True if disturbed
        """
        self.magnitude_history.append(field_magnitude)
        
        if len(self.magnitude_history) > self.max_history:
            self.magnitude_history.pop(0)
        
        if len(self.magnitude_history) < 20:
            return False
        
        # Compare to reference
        deviation = abs(field_magnitude - self.reference_magnitude)
        
        return deviation > self.threshold
    
    def update_reference(self, field_magnitude: float) -> None:
        """Update reference field magnitude."""
        self.reference_magnitude = 0.99 * self.reference_magnitude + 0.01 * field_magnitude


class Compass:
    """Complete compass sensor with calibration and filtering."""
    
    def __init__(self, config: Optional[CompassConfig] = None):
        self.config = config or CompassConfig()
        
        # Components
        self.field_model = MagneticFieldModel()
        self.calibrator = MagnetometerCalibrator()
        self.tilt_comp = TiltCompensatedHeading(config)
        self.disturbance_detector = DisturbanceDetector(config)
        
        # Filtered heading
        self.filtered_heading = 0.0
        self.heading_filter_alpha = 0.2
        
        # Quality tracking
        self.quality = 1.0
    
    def read(
        self,
        mag_raw: NDArray,
        accel: NDArray,
        temperature: float = 25.0
    ) -> CompassReading:
        """Process compass reading.
        
        Args:
            mag_raw: Raw magnetometer reading (body frame)
            accel: Accelerometer reading for tilt compensation
            temperature: Temperature for compensation
            
        Returns:
            Processed CompassReading
        """
        # Update tilt angles
        self.tilt_comp.update_attitude(accel)
        
        # Apply calibration
        mag_corrected = self.calibrator.correct(mag_raw)
        
        # Compute heading with tilt compensation
        heading = self.tilt_comp.compute_heading(
            mag_corrected,
            self.tilt_comp.pitch,
            self.tilt_comp.roll
        )
        
        # Apply magnetic declination
        heading += self.config.declination
        heading = (heading + 360) % 360
        
        # Low-pass filter heading
        self.filtered_heading = self._filter_heading(heading)
        
        # Check for disturbances
        field_magnitude = np.linalg.norm(mag_corrected)
        disturbed = self.disturbance_detector.check_disturbance(field_magnitude)
        
        if disturbed:
            self.disturbance_detector.update_reference(field_magnitude)
        
        # Compute quality
        self.quality = self._compute_quality(field_magnitude)
        
        return CompassReading(
            timestamp=time.time(),
            magnetic_field=mag_corrected,
            heading=self.filtered_heading,
            pitch=self.tilt_comp.pitch,
            roll=self.tilt_comp.roll,
            quality=self.quality,
            disturbance=disturbed
        )
    
    def _filter_heading(self, heading: float) -> float:
        """Filter heading to handle 0/360 discontinuity."""
        diff = heading - self.filtered_heading
        
        # Handle wrap-around
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360
        
        filtered = self.filtered_heading + self.heading_filter_alpha * diff
        
        return (filtered + 360) % 360
    
    def _compute_quality(self, field_magnitude: float) -> float:
        """Compute compass quality based on field consistency."""
        # Quality based on:
        # 1. Field magnitude consistency
        # 2. Tilt angles (high tilt = lower quality)
        # 3. Disturbance detection
        
        # Magnitude quality
        mag_deviation = abs(field_magnitude - self.config.reference_field)
        mag_quality = max(0, 1 - mag_deviation / 50)
        
        # Tilt quality
        tilt_magnitude = np.sqrt(self.tilt_comp.pitch**2 + self.tilt_comp.roll**2)
        tilt_quality = max(0, 1 - tilt_magnitude / 45)  # 45 degrees = 0 quality
        
        # Combined quality
        quality = 0.6 * mag_quality + 0.3 * tilt_quality
        
        if self.disturbance_detector.magnitude_history:
            if len(self.disturbance_detector.magnitude_history) > 50:
                recent = self.disturbance_detector.magnitude_history[-50:]
                std = np.std(recent)
                stability_quality = max(0, 1 - std / 5)
                quality = 0.7 * quality + 0.3 * stability_quality
        
        return np.clip(quality, 0, 1)
    
    def calibrate(self) -> Tuple[NDArray, NDArray]:
        """Run calibration with collected samples."""
        return self.calibrator.calibrate()
    
    def add_calibration_sample(self, measurement: NDArray) -> None:
        """Add sample for calibration."""
        self.calibrator.add_sample(measurement)


def demo_compass():
    """Demonstrate compass processing."""
    print("=" * 60)
    print("Compass Demo")
    print("=" * 60)
    
    # Create compass
    config = CompassConfig(
        model="QMC5883L",
        reference_field=45.0,
        declination=5.0  # East declination
    )
    compass = Compass(config)
    
    # Create field model for reference
    field_model = MagneticFieldModel(latitude=32.0, longitude=35.0)
    print(f"\nReference field: {field_model.get_magnitude():.1f} μT")
    print(f"Magnetic declination: {field_model.get_declination():.1f}°")
    
    # Simulate heading measurements
    print("\nSimulating heading measurements...")
    
    import random
    
    for heading_true in [0, 45, 90, 135, 180, 225, 270, 315]:
        # Create synthetic magnetometer data
        heading_rad = np.radians(heading_true)
        
        # True field (horizontal)
        true_field = np.array([
            np.cos(heading_rad),
            np.sin(heading_rad),
            0.4  # Slight downward component
        ]) * 45.0  # Field magnitude
        
        # Add hard iron offset
        hard_iron = np.array([2.0, -1.5, 0.5])
        
        # Add soft iron distortion
        soft_iron = np.array([
            [1.1, 0.05, 0],
            [0.05, 0.9, 0],
            [0, 0, 1.05]
        ])
        
        # Generate reading
        raw = soft_iron @ true_field + hard_iron + random.randn(3) * 2
        
        # Simulate accelerometer (level)
        accel = np.array([0, 0, 9.81])
        
        # Process
        reading = compass.read(raw, accel)
        
        error = reading.heading - heading_true
        if error > 180:
            error -= 360
        if error < -180:
            error += 360
        
        print(f"  True: {heading_true:3d}° -> Measured: {reading.heading:5.1f}°  "
              f"(error: {error:+.1f}°) quality={reading.quality:.2f}")
    
    # Test tilt compensation
    print("\n" + "=" * 40)
    print("Tilt Compensation Test")
    print("=" * 40)
    
    # Tilted orientation
    pitch = 15.0  # 15 degrees pitch
    roll = 10.0   # 10 degrees roll
    
    heading_true = 90.0
    heading_rad = np.radians(heading_true)
    
    # Field in body frame (rotated)
    true_field = np.array([
        np.cos(heading_rad),
        np.sin(heading_rad),
        0.4
    ]) * 45.0
    
    # Apply tilt rotation
    pitch_rad = np.radians(-pitch)
    roll_rad = np.radians(-roll)
    
    # Simplified tilt: just add some cross-axis coupling
    raw = true_field + random.randn(3) * 2
    raw[0] += roll * 0.5
    raw[1] += pitch * 0.5
    
    accel = np.array([
        -np.sin(pitch_rad) * 9.81,
        np.sin(roll_rad) * np.cos(pitch_rad) * 9.81,
        np.cos(roll_rad) * np.cos(pitch_rad) * 9.81
    ])
    
    reading = compass.read(raw, accel)
    
    print(f"  Pitch: {pitch}°, Roll: {roll}°")
    print(f"  True heading: {heading_true}° -> Measured: {reading.heading:.1f}°")
    print(f"  Estimated pitch: {reading.pitch:.1f}°, roll: {reading.roll:.1f}°")
    
    # Test disturbance detection
    print("\n" + "=" * 40)
    print("Disturbance Detection")
    print("=" * 40)
    
    # Normal field
    for i in range(50):
        mag = np.array([45 + random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1)])
        compass.read(mag, np.array([0, 0, 9.81]))
    
    print(f"  Normal field quality: {compass.quality:.2f}")
    
    # Disturbed field (nearby magnet)
    for i in range(20):
        mag = np.array([35 + random.uniform(-2, 2), random.uniform(-2, 2), random.uniform(-2, 2)])
        reading = compass.read(mag, np.array([0, 0, 9.81]))
        if i == 0:
            print(f"  Disturbed reading: heading={reading.heading:.1f}°, disturbed={reading.disturbance}")


if __name__ == "__main__":
    demo_compass()