"""Barometer sensor for altitude estimation.

Implements:
- Pressure to altitude conversion (barometric formula)
- Temperature compensation
- Sea level pressure calibration
- Noise filtering and smoothing
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple, List
import numpy as np
from numpy.typing import NDArray
import time


@dataclass
class BarometerConfig:
    """Barometer configuration."""
    model: str = "generic"
    
    # Operating range
    min_pressure: float = 200.0   # Pa
    max_pressure: float = 110000.0  # Pa
    
    # Calibration
    sea_level_pressure: float = 101325.0  # Pa (standard atmosphere)
    sea_level_temperature: float = 15.0  # Celsius
    
    # Noise parameters
    noise_std: float = 0.1  # Pa (typical BMP280: 0.03Pa RMS)
    
    # Update rate
    update_rate: float = 50.0  # Hz


@dataclass
class BarometerReading:
    """Barometer measurement."""
    timestamp: float
    pressure: float        # Pa
    temperature: float      # Celsius
    
    # Computed values
    altitude: float = 0.0   # m above sea level
    altitude_agl: float = 0.0  # m above ground level
    
    # Quality
    quality: float = 1.0   # 0-1 quality indicator


class BarometerModel:
    """Physical barometer model."""
    
    # Standard atmosphere constants
    LAPSED_RATE = 0.0065     # K/m (temperature lapse rate)
    GAS_CONSTANT = 287.05    # J/(kg·K)
    GRAVITY = 9.80665        # m/s²
    PRESSURE_ALTITUDE_FACTOR = 44330.77  # meters
    
    def __init__(self, config: Optional[BarometerConfig] = None):
        self.config = config or BarometerConfig()
        
        # Calibration
        self.calibrated_pressure = config.sea_level_pressure if config else 101325.0
        self.temperature_offset = 0.0
        
        # State
        self.last_pressure = 0.0
        self.pressure_trend = 0.0
    
    def pressure_to_altitude(
        self,
        pressure: float,
        reference_pressure: Optional[float] = None
    ) -> float:
        """Convert pressure to altitude using barometric formula.
        
        Uses international standard atmosphere:
          h = 44330.77 * (1 - (p/p0)^0.190284)
        
        Args:
            pressure: Current pressure in Pa
            reference_pressure: Reference pressure (sea level)
            
        Returns:
            Altitude in meters
        """
        if reference_pressure is None:
            reference_pressure = self.calibrated_pressure
        
        if pressure <= 0 or reference_pressure <= 0:
            return 0.0
        
        # International barometric formula
        ratio = pressure / reference_pressure
        
        if ratio <= 0:
            return 0.0
        
        altitude = self.PRESSURE_ALTITUDE_FACTOR * (1 - ratio ** 0.190284)
        
        return altitude
    
    def altitude_to_pressure(
        self,
        altitude: float,
        reference_pressure: Optional[float] = None
    ) -> float:
        """Convert altitude to pressure (inverse formula)."""
        if reference_pressure is None:
            reference_pressure = self.calibrated_pressure
        
        return reference_pressure * (1 - altitude / self.PRESSURE_ALTITUDE_FACTOR) ** 5.255
    
    def apply_temperature_compensation(
        self,
        pressure: float,
        temperature: float
    ) -> float:
        """Apply temperature compensation to pressure reading."""
        # Simplified temperature compensation
        # In reality, use calibration data from datasheet
        T_ref = self.config.sea_level_temperature + 273.15
        T_actual = temperature + 273.15 + self.temperature_offset
        
        # Pressure correction factor
        correction = T_actual / T_ref
        
        return pressure * correction
    
    def compute_density_altitude(
        self,
        pressure: float,
        temperature: float
    ) -> float:
        """Compute density altitude (accounts for non-standard temperature).
        
        Returns altitude that corresponds to standard atmosphere
        with same air density.
        """
        # Pressure altitude
        pressure_alt = self.pressure_to_altitude(pressure)
        
        # Density altitude correction
        # Uses virtual temperature concept
        ISA_temp = self.config.sea_level_temperature - self.LAPSED_RATE * pressure_alt
        actual_temp = temperature + 273.15
        
        # Density altitude correction (simplified)
        delta_T = actual_temp - ISA_temp
        density_correction = delta_T * 120  # Approximate factor
        
        return pressure_alt + density_correction


class BarometerFilter:
    """Kalman filter for barometer altitude estimation."""
    
    def __init__(self, config: Optional[BarometerConfig] = None):
        self.config = config or BarometerConfig()
        
        # State: [altitude, altitude_rate]
        self.state = np.zeros(2)
        
        # Covariance
        self.P = np.eye(2) * 10
        
        # Process noise
        self.Q = np.eye(2) * 0.01
        self.Q[1, 1] = 0.1  # Higher noise for velocity
        
        # Measurement noise
        self.R = config.noise_std ** 2 if config else 0.01
        
        # Last update time
        self.last_time: Optional[float] = None
    
    def predict(self, dt: float) -> None:
        """Predict step (constant velocity model)."""
        # State transition
        F = np.array([
            [1, dt],
            [0, 1]
        ])
        
        # Predict state and covariance
        self.state = F @ self.state
        self.P = F @ self.P @ F.T + self.Q
    
    def update(self, pressure: float, temperature: float) -> float:
        """Update with barometer reading.
        
        Returns:
            Filtered altitude estimate
        """
        # Compute altitude from pressure
        model = BarometerModel(self.config)
        altitude = model.pressure_to_altitude(pressure)
        
        # Measurement residual
        z = altitude
        H = np.array([[1, 0]])
        
        y = z - H @ self.state
        S = H @ self.P @ H.T + self.R
        K = self.P @ H.T / S
        
        # Update state
        self.state = self.state + K.flatten() * y
        self.P = (np.eye(2) - np.outer(K, H)) @ self.P
        
        return self.state[0]
    
    def get_state(self) -> Tuple[float, float]:
        """Get filtered altitude and vertical velocity."""
        return self.state[0], self.state[1]


class SeaLevelCalibration:
    """Sea level pressure calibration."""
    
    def __init__(self):
        self.samples = []
        self.max_samples = 1000
    
    def add_sample(
        self,
        pressure: float,
        altitude: float,
        gps_altitude: Optional[float] = None
    ) -> None:
        """Add calibration sample.
        
        Args:
            pressure: Barometer pressure (Pa)
            altitude: Known altitude (GPS or manual)
            gps_altitude: GPS altitude for fusion (optional)
        """
        self.samples.append({
            'pressure': pressure,
            'altitude': altitude,
            'gps_altitude': gps_altitude,
            'time': time.time()
        })
        
        if len(self.samples) > self.max_samples:
            self.samples.pop(0)
    
    def calibrate(self) -> float:
        """Compute calibrated sea level pressure.
        
        Returns:
            Sea level pressure in Pa
        """
        if len(self.samples) < 10:
            return 101325.0  # Standard atmosphere
        
        # Use GPS altitude if available, otherwise use known altitude
        altitudes = []
        pressures = []
        
        for sample in self.samples:
            if sample['gps_altitude'] is not None:
                alt = sample['gps_altitude']
            else:
                alt = sample['altitude']
            
            altitudes.append(alt)
            pressures.append(sample['pressure'])
        
        # Compute sea level pressure for each sample
        sea_level_pressures = []
        model = BarometerModel()
        
        for p, h in zip(pressures, altitudes):
            # Inverse barometric formula
            p0 = p * (1 - h / model.PRESSURE_ALTITUDE_FACTOR) ** (-5.255)
            sea_level_pressures.append(p0)
        
        # Average (with outlier rejection)
        pressures_arr = np.array(sea_level_pressures)
        
        # Reject outliers (>2 std)
        mean = np.mean(pressures_arr)
        std = np.std(pressures_arr)
        
        valid = np.abs(pressures_arr - mean) < 2 * std
        calibrated = np.mean(pressures_arr[valid])
        
        return calibrated
    
    def reset(self) -> None:
        """Reset calibration data."""
        self.samples = []


class Barometer:
    """Complete barometer sensor with filtering and calibration."""
    
    def __init__(self, config: Optional[BarometerConfig] = None):
        self.config = config or BarometerConfig()
        
        # Components
        self.model = BarometerModel(config)
        self.filter = BarometerFilter(config)
        self.calibration = SeaLevelCalibration()
        
        # Ground level reference
        self.ground_pressure: Optional[float] = None
        self.ground_altitude: float = 0.0
        self.ground_set = False
        
        # Reading history
        self.history: List[BarometerReading] = []
        self.max_history = 1000
    
    def read(
        self,
        pressure: float,
        temperature: float,
        dt: float = 0.02
    ) -> BarometerReading:
        """Process barometer reading.
        
        Args:
            pressure: Raw pressure in Pa
            temperature: Temperature in Celsius
            dt: Time step since last reading
            
        Returns:
            Processed BarometerReading
        """
        # Temperature compensation
        compensated_pressure = self.model.apply_temperature_compensation(
            pressure, temperature
        )
        
        # Update Kalman filter
        self.filter.predict(dt)
        filtered_altitude = self.filter.update(compensated_pressure, temperature)
        
        # Compute altitude above sea level
        altitude_sea = filtered_altitude
        
        # Compute altitude above ground
        if self.ground_set:
            altitude_agl = altitude_sea - self.ground_altitude
        else:
            altitude_agl = altitude_sea
        
        # Compute quality based on consistency
        quality = self._compute_quality()
        
        reading = BarometerReading(
            timestamp=time.time(),
            pressure=compensated_pressure,
            temperature=temperature,
            altitude=altitude_sea,
            altitude_agl=altitude_agl,
            quality=quality
        )
        
        self.history.append(reading)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        return reading
    
    def _compute_quality(self) -> float:
        """Compute reading quality (0-1)."""
        if len(self.history) < 10:
            return 0.5
        
        # Check pressure consistency
        recent = self.history[-20:]
        pressures = [r.pressure for r in recent]
        std = np.std(pressures)
        
        # Lower variance = higher quality
        quality = np.exp(-std / 0.5)
        
        return np.clip(quality, 0, 1)
    
    def set_ground_level(self, pressure: float, altitude: float) -> None:
        """Set ground level reference.
        
        Args:
            pressure: Current pressure at ground
            altitude: Ground altitude (GPS)
        """
        self.ground_pressure = pressure
        self.ground_altitude = altitude
        self.ground_set = True
    
    def calibrate_sea_level(self) -> float:
        """Calibrate sea level pressure from samples."""
        calibrated = self.calibration.calibrate()
        self.model.calibrated_pressure = calibrated
        return calibrated
    
    def add_calibration_sample(
        self,
        pressure: float,
        altitude: float,
        gps_altitude: Optional[float] = None
    ) -> None:
        """Add sample for sea level calibration."""
        self.calibration.add_sample(pressure, altitude, gps_altitude)


def demo_barometer():
    """Demonstrate barometer processing."""
    print("=" * 60)
    print("Barometer Demo")
    print("=" * 60)
    
    # Create barometer
    config = BarometerConfig(model="BMP280")
    baro = Barometer(config)
    
    # Simulate ground level
    print("\nSetting ground level...")
    baro.set_ground_level(101325.0, 100.0)
    print(f"  Ground altitude: {baro.ground_altitude}m")
    
    # Simulate altitude changes
    print("\nSimulating altitude profile...")
    
    import random
    dt = 0.02
    times = []
    altitudes = []
    
    # Simulate climbing
    for i in range(500):
        t = i * dt
        
        # True altitude (climbing then hovering)
        if t < 10:
            true_alt = 100 + t * 5  # Climb 5 m/s
        else:
            true_alt = 150 + random.uniform(-0.5, 0.5)
        
        # True pressure
        true_pressure = BarometerModel().altitude_to_pressure(true_alt, 101325.0)
        
        # Add noise
        pressure = true_pressure + random.gauss(0, 0.1)
        temperature = 15 + 0.0065 * true_alt + random.gauss(0, 0.5)
        
        reading = baro.read(pressure, temperature, dt)
        
        if i % 50 == 0:
            print(f"  t={t:.1f}s: alt={reading.altitude:.1f}m, "
                  f"agl={reading.altitude_agl:.1f}m, quality={reading.quality:.2f}")
        
        times.append(t)
        altitudes.append(reading.altitude)
    
    # Calibrate sea level
    print("\n" + "=" * 40)
    print("Sea Level Calibration")
    print("=" * 40)
    
    # Add samples
    for i, (t, p) in enumerate(zip(times[::50], altitudes[::50] * 100)):
        baro.add_calibration_sample(
            pressure=101325.0 - i * 50,  # Simulated pressure
            altitude=i * 0.5,
            gps_altitude=i * 0.5
        )
    
    sea_level_p = baro.calibrate_sea_level()
    print(f"  Calibrated sea level pressure: {sea_level_p:.1f} Pa")
    
    # Final quality check
    print("\nFinal statistics:")
    recent = baro.history[-100:]
    alt_std = np.std([r.altitude for r in recent])
    print(f"  Altitude standard deviation: {alt_std:.2f}m")
    print(f"  Samples collected: {len(baro.history)}")


if __name__ == "__main__":
    demo_barometer()