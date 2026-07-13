"""IMU (Inertial Measurement Unit) sensor interface.

Implements:
- Accelerometer and gyroscope data processing
- Temperature compensation
- Calibration routines
- Noise filtering
- Unit conversion (raw -> SI)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
import numpy as np
from numpy.typing import NDArray
import time


@dataclass
class IMUConfig:
    """IMU sensor configuration."""
    # Sensor parameters
    model: str = "generic"
    
    # Scale factors (raw to SI units)
    accel_scale: float = 1.0 / 16384.0  # Default for MPU6000 (±2g)
    gyro_scale: float = 1.0 / 16384.0 * np.pi / 180  # rad/s
    
    # Range limits
    accel_range: float = 16.0   # g
    gyro_range: float = 2000.0  # deg/s
    
    # Calibration
    accel_bias: NDArray = field(default_factory=lambda: np.zeros(3))
    gyro_bias: NDArray = field(default_factory=lambda: np.zeros(3))
    
    # Orientation (rotation from body to sensor frame)
    orientation: NDArray = field(default_factory=lambda: np.eye(3))
    
    # Noise parameters
    accel_noise_density: float = 0.04   # mg/sqrt(Hz)
    gyro_noise_density: float = 0.01    # deg/s/sqrt(Hz)
    
    # Update rate
    update_rate: float = 100.0  # Hz


@dataclass
class IMUReading:
    """IMU sensor reading."""
    timestamp: float
    accel: NDArray  # m/s² (3,)
    gyro: NDArray   # rad/s (3,)
    temperature: float = 25.0  # Celsius
    
    # Quality indicators
    accel_magnitude: float = 0.0
    gyro_magnitude: float = 0.0
    
    # Raw values (before calibration)
    accel_raw: Optional[NDArray] = None
    gyro_raw: Optional[NDArray] = None
    
    def is_valid(self, min_accel: float = 0.5, max_accel: float = 20.0) -> bool:
        """Check if reading is physically plausible."""
        return min_accel <= self.accel_magnitude <= max_accel


class IMUFusion:
    """IMU data fusion and processing."""
    
    def __init__(self, config: Optional[IMUConfig] = None):
        self.config = config or IMUConfig()
        
        # State
        self.accel_bias = config.accel_bias if config else np.zeros(3)
        self.gyro_bias = config.gyro_bias if config else np.zeros(3)
        
        # Calibration data
        self.calibration_time: Optional[float] = None
        self.samples_collected = 0
        
        # Filtering
        self.accel_filter = ComplementaryFilter(alpha=0.1)
        self.gyro_filter = ComplementaryFilter(alpha=0.02)
        
        # Temperature compensation
        self.temp_coeff_accel = np.zeros((3, 3))  # Per-degree scale factor change
        self.temp_coeff_gyro = np.zeros((3, 3))
        
        # Quality tracking
        self.quality_score = 1.0
        self.reading_count = 0
    
    def process_raw(
        self,
        accel_raw: NDArray,
        gyro_raw: NDArray,
        temperature: float = 25.0
    ) -> IMUReading:
        """Process raw IMU data.
        
        Args:
            accel_raw: Raw accelerometer (3,) - typically 16-bit integers
            gyro_raw: Raw gyroscope (3,) - typically 16-bit integers
            temperature: Temperature in Celsius
            
        Returns:
            Calibrated IMUReading
        """
        self.reading_count += 1
        
        # Convert to floats
        accel = accel_raw.astype(float)
        gyro = gyro_raw.astype(float)
        
        # Apply scale factors
        accel = accel * self.config.accel_scale * 9.81  # Convert to m/s²
        gyro = gyro * self.config.gyro_scale  # Convert to rad/s
        
        # Apply orientation rotation
        if not np.array_equal(self.config.orientation, np.eye(3)):
            accel = self.config.orientation @ accel
            gyro = self.config.orientation @ gyro
        
        # Temperature compensation
        temp_diff = temperature - 25.0
        accel = accel * (1 + self.temp_coeff_accel @ np.ones(3) * temp_diff)
        gyro = gyro * (1 + self.temp_coeff_gyro @ np.ones(3) * temp_diff)
        
        # Apply bias correction
        accel = accel - self.accel_bias
        gyro = gyro - self.gyro_bias
        
        # Filter outliers
        accel = self.accel_filter.update(accel)
        gyro = self.gyro_filter.update(gyro)
        
        # Compute magnitudes
        accel_mag = np.linalg.norm(accel)
        gyro_mag = np.linalg.norm(gyro)
        
        return IMUReading(
            timestamp=time.time(),
            accel=accel,
            gyro=gyro,
            temperature=temperature,
            accel_magnitude=accel_mag,
            gyro_magnitude=gyro_mag,
            accel_raw=accel_raw,
            gyro_raw=gyro_raw
        )
    
    def calibrate(self, samples: List[IMUReading], method: str = "static") -> bool:
        """Calibrate IMU using collected samples.
        
        Args:
            samples: List of IMU readings collected while stationary
            method: "static" for stationary calibration
            
        Returns:
            True if calibration successful
        """
        if len(samples) < 100:
            print(f"Not enough samples: {len(samples)} < 100")
            return False
        
        # Compute average bias (assumes stationary)
        avg_accel = np.zeros(3)
        avg_gyro = np.zeros(3)
        
        for reading in samples:
            if reading.is_valid():
                avg_accel += reading.accel
                avg_gyro += reading.gyro
        
        avg_accel /= len(samples)
        avg_gyro /= len(samples)
        
        # Expected: accel = [0, 0, g], gyro = [0, 0, 0]
        gravity = 9.81
        expected_accel = np.array([0, 0, gravity])
        
        # Compute bias
        self.accel_bias = avg_accel - expected_accel
        self.gyro_bias = avg_gyro
        
        self.calibration_time = time.time()
        self.samples_collected = len(samples)
        
        print(f"IMU calibrated with {len(samples)} samples")
        print(f"  Accel bias: {self.accel_bias}")
        print(f"  Gyro bias: {self.gyro_bias}")
        
        return True
    
    def estimate_quality(self, recent_readings: List[IMUReading]) -> float:
        """Estimate IMU data quality.
        
        Args:
            recent_readings: Last N readings
            
        Returns:
            Quality score 0-1
        """
        if len(recent_readings) < 10:
            return 0.5
        
        # Check accelerometer variance (should be low when stationary)
        accels = np.array([r.accel for r in recent_readings[-20:]])
        accel_variance = np.var(accels, axis=0).mean()
        
        # Check gyroscope variance
        gyros = np.array([r.gyro for r in recent_readings[-20:]])
        gyro_variance = np.var(gyros, axis=0).mean()
        
        # Quality based on variance thresholds
        accel_threshold = 0.1  # m/s² variance
        gyro_threshold = 0.01  # rad/s variance
        
        accel_quality = np.exp(-accel_variance / accel_threshold)
        gyro_quality = np.exp(-gyro_variance / gyro_threshold)
        
        self.quality_score = 0.5 * accel_quality + 0.5 * gyro_quality
        
        return self.quality_score


class ComplementaryFilter:
    """Complementary filter for IMU data smoothing."""
    
    def __init__(self, alpha: float = 0.1):
        self.alpha = alpha
        self.value = None
        self.count = 0
    
    def update(self, new_value: NDArray) -> NDArray:
        """Update filter with new value."""
        if self.value is None:
            self.value = new_value.copy()
        else:
            self.value = self.alpha * new_value + (1 - self.alpha) * self.value
        
        self.count += 1
        return self.value.copy()
    
    def reset(self) -> None:
        """Reset filter state."""
        self.value = None
        self.count = 0


class AccelerometerModel:
    """Physical accelerometer model with scale/bias/misalignment."""
    
    def __init__(self):
        # Scale factors per axis
        self.scale = np.ones(3)
        
        # Bias per axis
        self.bias = np.zeros(3)
        
        # Misalignment matrix (upper triangular, 3x3)
        self.misalignment = np.eye(3)
        
        # Non-linearity coefficients
        self.nonlinearity = np.zeros(3)
    
    def calibrate(
        self,
        measurements: List[Tuple[NDArray, NDArray]]  # [(true, measured), ...]
    ) -> float:
        """Calibrate using known reference values.
        
        Returns:
            RMS error after calibration
        """
        if len(measurements) < 3:
            return float('inf')
        
        # Build observation matrix
        H = []
        y = []
        
        for true_val, measured in measurements:
            # Simplified model: y = scale * (misalignment @ measured + bias) + nonlinearity
            # Linearize for initial calibration
            for i in range(3):
                H.append([measured[0], measured[1], measured[2], 1, 0, 0, 0, 0, 0, 0])
                H.append([0, 0, 0, 0, measured[0], measured[1], measured[2], 1, 0, 0])
                H.append([0, 0, 0, 0, 0, 0, 0, 0, measured[0], measured[1], measured[2], 1])
                y.append([true_val[0], true_val[1], true_val[2]])
        
        H = np.array(H)
        y = np.array(y).flatten()
        
        # Solve least squares
        x, residuals, rank, s = np.linalg.lstsq(H, y, rcond=None)
        
        # Extract parameters (simplified)
        self.scale = 1 + x[0:3]
        self.bias = x[3:6]
        self.misalignment = np.eye(3) + np.array([
            [0, x[6], x[7]],
            [x[8], 0, x[9]],
            [x[10], x[11], 0]
        ])
        
        return np.sqrt(np.mean(residuals**2)) if len(residuals) > 0 else 0
    
    def correct(self, measured: NDArray) -> NDArray:
        """Apply calibration correction."""
        corrected = self.misalignment @ measured
        corrected = self.scale * corrected + self.bias
        corrected += self.nonlinearity * (measured ** 2)
        return corrected


class GyroscopeModel:
    """Physical gyroscope model."""
    
    def __init__(self):
        self.scale = np.ones(3)
        self.bias = np.zeros(3)
        self.misalignment = np.eye(3)
        
        # Temperature compensation
        self.temp_poly = [np.zeros(3), np.zeros(3), np.zeros(3)]  # [a0, a1*T, a2*T²]
    
    def calibrate(self, measurements: List[Tuple[NDArray, NDArray]]) -> bool:
        """Calibrate gyroscope."""
        # Simplified: assume zero rate when stationary
        biases = []
        
        for true_val, measured in measurements:
            # Should be zero when stationary
            if np.linalg.norm(true_val) < 0.01:  # Truly stationary
                biases.append(measured)
        
        if len(biases) < 10:
            return False
        
        self.bias = np.mean(biases, axis=0)
        
        return True
    
    def correct(self, measured: NDArray, temperature: float = 25.0) -> NDArray:
        """Apply temperature-compensated correction."""
        # Temperature compensation
        temp_effect = (self.temp_poly[0] + 
                      self.temp_poly[1] * temperature + 
                      self.temp_poly[2] * temperature**2)
        
        corrected = self.misalignment @ measured
        corrected = self.scale * corrected
        corrected = corrected - self.bias - temp_effect
        
        return corrected


class IMUSimulator:
    """Simulate IMU data for testing."""
    
    def __init__(self, config: Optional[IMUConfig] = None):
        self.config = config or IMUConfig()
        
        self.last_time = None
        self.noise_state = np.zeros(6)  # Random walk state
    
    def generate(
        self,
        true_angular_velocity: NDArray,
        true_acceleration: NDArray,
        dt: float
    ) -> Tuple[NDArray, NDArray]:
        """Generate simulated IMU readings.
        
        Args:
            true_angular_velocity: True angular velocity (rad/s)
            true_acceleration: True acceleration (m/s²)
            dt: Time step
            
        Returns:
            (accel, gyro) readings
        """
        # Process noise (random walk)
        noise_std = np.array([
            self.config.accel_noise_density * np.sqrt(dt),
            self.config.accel_noise_density * np.sqrt(dt),
            self.config.accel_noise_density * np.sqrt(dt),
            self.config.gyro_noise_density * np.sqrt(dt) * np.pi / 180,
            self.config.gyro_noise_density * np.sqrt(dt) * np.pi / 180,
            self.config.gyro_noise_density * np.sqrt(dt) * np.pi / 180
        ])
        
        self.noise_state += np.random.randn(6) * noise_std
        
        # Add noise to measurements
        accel = true_acceleration + self.noise_state[:3]
        gyro = true_angular_velocity + self.noise_state[3:]
        
        # Add constant bias
        accel += self.config.accel_bias
        gyro += self.config.gyro_bias
        
        return accel, gyro


def demo_imu():
    """Demonstrate IMU processing."""
    print("=" * 60)
    print("IMU Processing Demo")
    print("=" * 60)
    
    # Create IMU
    config = IMUConfig(
        model="MPU6000",
        accel_scale=1.0 / 16384.0,
        gyro_scale=1.0 / 16384.0 * np.pi / 180,
        accel_bias=np.array([0.01, -0.02, 0.005]),
        gyro_bias=np.array([0.001, -0.002, 0.0005])
    )
    
    imu = IMUFusion(config)
    
    # Generate simulated data
    simulator = IMUSimulator(config)
    
    # Simulate hover (zero angular velocity, gravity + accel)
    print("\nSimulating hover state...")
    
    samples = []
    for i in range(200):
        dt = 0.01
        true_gyro = np.zeros(3)
        true_accel = np.array([0, 0, 9.81])  # Gravity
        
        accel, gyro = simulator.generate(true_gyro, true_accel, dt)
        
        # Convert to integer (模拟原始数据)
        accel_raw = (accel / (config.accel_scale * 9.81)).astype(int)
        gyro_raw = (gyro / config.gyro_scale / np.pi * 180).astype(int)
        
        reading = imu.process_raw(accel_raw, gyro_raw, temperature=25.0)
        samples.append(reading)
        
        if i % 50 == 0:
            print(f"  Sample {i}: accel=({reading.accel[0]:.3f}, {reading.accel[1]:.3f}, {reading.accel[2]:.3f})")
    
    # Calibrate
    print("\nCalibrating...")
    success = imu.calibrate(samples)
    print(f"Calibration: {'SUCCESS' if success else 'FAILED'}")
    
    # Check quality
    quality = imu.estimate_quality(samples)
    print(f"Data quality: {quality:.2%}")
    
    # Test data processing
    print("\nProcessing new data...")
    accel_raw = np.array([100, -200, 16000])  # Example raw values
    gyro_raw = np.array([10, -20, 5])
    
    reading = imu.process_raw(accel_raw, gyro_raw, temperature=25.0)
    print(f"  Corrected accel: {reading.accel}")
    print(f"  Corrected gyro: {reading.gyro}")
    print(f"  Valid: {reading.is_valid()}")


if __name__ == "__main__":
    demo_imu()