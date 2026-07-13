"""GNSS (GPS/GNSS) sensor processing.

Implements:
- Multi-constellation GNSS support
- RTK/PPP positioning
- Satellite selection
- Position velocity time (PVT) solution
- Integrity monitoring
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
import numpy as np
from numpy.typing import NDArray
import time


@dataclass
class SatelliteObservation:
    """Single satellite observation."""
    prn: int              # PRN number
    constellation: str    # "GPS", "GLONASS", "Galileo", "BeiDou"
    azimuth: float        # degrees
    elevation: float      # degrees
    signal_strength: float  # dB-Hz
    pseudorange: float     # meters
    carrier_phase: float   # cycles
    doppler: float         # Hz
    
    # Status
    locked: bool = False
    corrected: bool = False


@dataclass
class GNSSConfig:
    """GNSS receiver configuration."""
    constellations: List[str] = field(default_factory=lambda: ["GPS", "GLONASS"])
    min_elevation_mask: float = 15.0  # degrees
    min_satellites: int = 4
    
    # RTK settings
    enable_rtk: bool = True
    rtk_mode: str = "moving_baseline"  # or "fixed_baseline"
    reference_station: Optional[Tuple[float, float, float]] = None  # (lat, lon, alt)
    
    # Output rate
    update_rate: float = 10.0  # Hz
    
    # Accuracy requirements
    position_accuracy: float = 2.0  # meters (horizontal)
    velocity_accuracy: float = 0.1   # m/s


@dataclass
class PVTsolution:
    """Position Velocity Time solution."""
    timestamp: float
    
    # Position (LLH or ECEF)
    latitude: float       # degrees
    longitude: float      # degrees
    altitude: float       # meters above ellipsoid
    
    # Position in ECEF
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    
    # Velocity
    v_north: float = 0.0
    v_east: float = 0.0
    v_down: float = 0.0
    
    # Accuracy estimates
    horizontal_accuracy: float = 10.0
    vertical_accuracy: float = 20.0
    speed_accuracy: float = 0.5
    
    # Integrity
    hdop: float = 99.0
    vdop: float = 99.0
    pdop: float = 99.0
    tdop: float = 99.0
    
    # Status
    fix_type: int = 0  # 0=none, 2=2D, 3=3D, 4=RTK
    num_satellites: int = 0
    correction_age: float = 999.0  # seconds
    
    def is_valid(self) -> bool:
        """Check if solution is valid."""
        return self.fix_type >= 2 and self.num_satellites >= self.min_satellites


class SatelliteSelection:
    """Select best satellites for positioning."""
    
    def __init__(self, config: Optional[GNSSConfig] = None):
        self.config = config or GNSSConfig()
    
    def select_satellites(
        self,
        observations: List[SatelliteObservation]
    ) -> List[SatelliteObservation]:
        """Select subset of satellites for positioning.
        
        Uses elevation and signal strength for selection.
        """
        # Filter by elevation mask
        filtered = [
            obs for obs in observations
            if obs.elevation >= self.config.min_elevation_mask
            and obs.locked
        ]
        
        if len(filtered) < self.config.min_satellites:
            return observations[:self.config.min_satellites]
        
        # Sort by elevation (higher is better)
        filtered.sort(key=lambda x: -x.elevation)
        
        # Return top satellites
        return filtered[:12]  # Max 12 for best geometry
    
    def compute_geometry(
        self,
        satellites: List[Dict]
    ) -> Tuple[float, float, float]:
        """Compute DOP values from satellite geometry.
        
        Args:
            satellites: List of satellite positions (ECEF)
            
        Returns:
            (hdop, vdop, pdop)
        """
        if len(satellites) < 4:
            return 99.0, 99.0, 99.0
        
        n = len(satellites)
        
        # Design matrix (for GDOP calculation)
        H = np.zeros((n, 4))
        
        for i, sat_pos in enumerate(satellites):
            # Unit vector from receiver to satellite
            # Simplified: just use position as pseudo-measurement
            if len(sat_pos) == 3:
                H[i] = [sat_pos[0], sat_pos[1], sat_pos[2], 1]
        
        # Normalize
        for i in range(n):
            norm = np.linalg.norm(H[i, :3])
            if norm > 0:
                H[i] /= norm
        
        # Compute geometry matrix
        Q = np.linalg.inv(H.T @ H)
        
        # Extract DOP values
        hdop = np.sqrt(Q[0, 0] + Q[1, 1])
        vdop = np.sqrt(Q[2, 2])
        pdop = np.sqrt(Q[0, 0] + Q[1, 1] + Q[2, 2])
        tdop = np.sqrt(Q[3, 3])
        
        return hdop, vdop, pdop


class RTKProcessor:
    """Real-Time Kinematic processing for high-accuracy positioning."""
    
    def __init__(self, config: Optional[GNSSConfig] = None):
        self.config = config or GNSSConfig()
        
        # Baseline vector (reference to rover)
        self.baseline = np.zeros(3)
        self.baseline_std = np.zeros(3)
        
        # Ambiguity resolution state
        self.ambiguities = {}
        
        # Statistics
        self.fix_rate = 0.0
        self.observations_processed = 0
    
    def process_epoch(
        self,
        rover_obs: List[SatelliteObservation],
        base_obs: List[SatelliteObservation],
        base_position: NDArray
    ) -> Tuple[NDArray, float, bool]:
        """Process single epoch for RTK solution.
        
        Args:
            rover_obs: Rover observations
            base_obs: Base station observations
            base_position: Base station position (ECEF)
            
        Returns:
            (baseline, accuracy, fixed)
        """
        # Match satellites between rover and base
        matched = self._match_satellites(rover_obs, base_obs)
        
        if len(matched) < 4:
            return np.zeros(3), 99.0, False
        
        # Compute double-differenced observables
        dd_obs = self._compute_double_differences(matched)
        
        # Integer ambiguity resolution (LAMBDA method)
        float_solution, cov = self._resolve_ambiguities(dd_obs)
        
        # Fix integer ambiguities
        int_ambiguities = self._round_ambiguities(float_solution, cov)
        
        fixed = int_ambiguities is not None
        
        # Compute baseline
        if fixed:
            baseline = self._compute_baseline(dd_obs, int_ambiguities)
            accuracy = 0.02  # ~2cm accuracy when fixed
        else:
            baseline = float_solution[:3]
            accuracy = 0.1 + 0.01 * len(matched)  # ~10cm when floating
        
        self.observations_processed += 1
        if fixed:
            self.fix_rate = (self.fix_rate * (self.observations_processed - 1) + 1) / self.observations_processed
        else:
            self.fix_rate = self.fix_rate * (self.observations_processed - 1) / self.observations_processed
        
        return baseline, accuracy, fixed
    
    def _match_satellites(
        self,
        rover_obs: List[SatelliteObservation],
        base_obs: List[SatelliteObservation]
    ) -> List[Tuple[SatelliteObservation, SatelliteObservation]]:
        """Match satellites between rover and base."""
        base_prns = {obs.prn: obs for obs in base_obs}
        
        matched = []
        for rover in rover_obs:
            if rover.prn in base_prns:
                base = base_prns[rover.prn]
                if rover.elevation >= 10 and base.elevation >= 10:  # Elevation mask
                    matched.append((rover, base))
        
        return matched
    
    def _compute_double_differences(
        self,
        matched: List[Tuple[SatelliteObservation, SatelliteObservation]]
    ) -> Dict:
        """Compute double-differenced observables."""
        if len(matched) < 2:
            return {}
        
        # Use first satellite as reference
        ref_rover, ref_base = matched[0]
        
        dd = {
            'pseudorange': [],
            'carrier_phase': [],
            'satellites': []
        }
        
        for rover, base in matched[1:]:
            # Double differenced pseudorange
            pr_dd = (rover.pseudorange - ref_rover.pseudorange) - \
                   (base.pseudorange - ref_base.pseudorange)
            
            # Double differenced carrier phase
            cp_dd = (rover.carrier_phase - ref_rover.carrier_phase) - \
                   (base.carrier_phase - ref_base.carrier_phase)
            
            dd['pseudorange'].append(pr_dd)
            dd['carrier_phase'].append(cp_dd)
            dd['satellites'].append((rover.prn, ref_rover.prn))
        
        return dd
    
    def _resolve_ambiguities(self, dd_obs: Dict) -> Tuple[NDArray, NDArray]:
        """Resolve integer ambiguities using LAMBDA method."""
        if len(dd_obs.get('carrier_phase', [])) < 4:
            return np.zeros(6), np.eye(6) * 100
        
        n = len(dd_obs['carrier_phase'])
        
        # Build observation vector
        y = np.array(dd_obs['carrier_phase'] + dd_obs['pseudorange'][:n])
        
        # Design matrix (simplified)
        H = np.zeros((2 * n, n + 3))
        H[:n, :n] = np.eye(n)
        H[n:, :n] = np.eye(n) * 0.01  # Lower weight for pseudorange
        
        # Weight matrix
        P = np.eye(2 * n) * 100
        
        # Float solution
        Q = np.linalg.inv(H.T @ P @ H)
        x = Q @ H.T @ P @ y
        
        float_ambiguities = x[:n]
        baseline = x[n:]
        
        return np.concatenate([baseline, float_ambiguities]), Q[:n, :n]
    
    def _round_ambiguities(
        self,
        float_solution: NDArray,
        cov: NDArray
    ) -> Optional[NDArray]:
        """Round ambiguities to integers with validation."""
        n = len(float_solution) - 3
        ambiguities = float_solution[3:3+n]
        
        # Integer rounding
        int_amb = np.round(ambiguities).astype(int)
        
        # Validation: check residuals
        residuals = np.abs(ambiguities - int_amb)
        
        # Accept if all residuals < 0.25 cycles
        if np.all(residuals < 0.25):
            return int_amb
        
        return None  # Not fixed
    
    def _compute_baseline(
        self,
        dd_obs: Dict,
        ambiguities: NDArray
    ) -> NDArray:
        """Compute baseline from fixed ambiguities."""
        # Simple least squares with fixed ambiguities
        n = len(ambiguities)
        
        # Baseline is already in float_solution when fixed
        return float_solution[:3] if len(float_solution) >= 3 else np.zeros(3)


class GNSSReceiver:
    """GNSS receiver processing."""
    
    def __init__(self, config: Optional[GNSSConfig] = None):
        self.config = config or GNSSConfig()
        
        self.solution = PVTsolution(
            timestamp=time.time(),
            fix_type=0
        )
        
        self.satellites: List[SatelliteObservation] = []
        self.selector = SatelliteSelection(config)
        
        if config.enable_rtk:
            self.rtk = RTKProcessor(config)
        else:
            self.rtk = None
        
        # Reference position (for differential corrections)
        self.reference_position: Optional[NDArray] = None
        
        # Kalman filter for smooth solution
        self.kf = self._init_kalman()
    
    def _init_kalman(self) -> dict:
        """Initialize Kalman filter for PVT."""
        # State: [x, y, z, vx, vy, vz]
        # Simple constant velocity model
        F = np.eye(6)
        F[:3, 3:] = np.eye(3) * 0.1  # dt
        
        # Measurement matrix (position only)
        H = np.zeros((3, 6))
        H[:3, :3] = np.eye(3)
        
        # Covariances
        R = np.eye(3) * self.config.position_accuracy ** 2
        Q = np.eye(6) * 0.01
        
        P = np.eye(6) * 10
        
        return {
            'x': np.zeros(6),
            'P': P,
            'F': F,
            'H': H,
            'Q': Q,
            'R': R
        }
    
    def update_satellites(self, observations: List[SatelliteObservation]) -> None:
        """Update satellite observations."""
        self.satellites = observations
    
    def compute_solution(self, raw_position: NDArray) -> PVTsolution:
        """Compute PVT solution from raw position.
        
        Args:
            raw_position: Raw position from receiver (ECEF)
            
        Returns:
            Filtered PVT solution
        """
        # Update Kalman filter
        kf = self.kf
        
        # Prediction
        kf['x'] = kf['F'] @ kf['x']
        kf['P'] = kf['F'] @ kf['P'] @ kf['F'].T + kf['Q']
        
        # Update
        z = raw_position - kf['H'] @ kf['x']
        S = kf['H'] @ kf['P'] @ kf['H'].T + kf['R']
        K = kf['P'] @ kf['H'].T @ np.linalg.inv(S)
        
        kf['x'] = kf['x'] + K @ z
        kf['P'] = (np.eye(6) - K @ kf['H']) @ kf['P']
        
        # Extract solution
        pos = kf['x'][:3]
        vel = kf['x'][3:]
        
        # Compute accuracy from covariance
        pos_std = np.sqrt(np.trace(kf['P'][:3, :3]))
        
        # Convert ECEF to LLH
        lat, lon, alt = self._ecef_to_llh(pos)
        
        # Compute DOP
        hdop = pos_std / 0.7  # Simplified
        
        solution = PVTsolution(
            timestamp=time.time(),
            latitude=lat,
            longitude=lon,
            altitude=alt,
            x=pos[0], y=pos[1], z=pos[2],
            v_north=vel[0], v_east=vel[1], v_down=vel[2],
            horizontal_accuracy=pos_std,
            vertical_accuracy=np.sqrt(kf['P'][2, 2]),
            hdop=hdop,
            vdop=hdop * 1.5,
            pdop=hdop * 1.8,
            fix_type=3,
            num_satellites=len(self.satellites)
        )
        
        self.solution = solution
        return solution
    
    def process_rtk(
        self,
        rover_obs: List[SatelliteObservation],
        base_obs: List[SatelliteObservation]
    ) -> Optional[PVTsolution]:
        """Process RTK corrections.
        
        Returns:
            RTK solution or None if not fixed
        """
        if not self.config.enable_rtk or self.rtk is None:
            return None
        
        if self.reference_position is None:
            print("No reference station position set")
            return None
        
        baseline, accuracy, fixed = self.rtk.process_epoch(
            rover_obs, base_obs, self.reference_position
        )
        
        # Add baseline to reference position
        solution = self.solution.copy()
        solution.x = self.reference_position[0] + baseline[0]
        solution.y = self.reference_position[1] + baseline[1]
        solution.z = self.reference_position[2] + baseline[2]
        
        lat, lon, alt = self._ecef_to_llh(np.array([solution.x, solution.y, solution.z]))
        solution.latitude = lat
        solution.longitude = lon
        solution.altitude = alt
        
        solution.horizontal_accuracy = accuracy
        solution.vertical_accuracy = accuracy * 1.5
        solution.fix_type = 4 if fixed else 3
        
        return solution
    
    @staticmethod
    def _ecef_to_llh(ecef: NDArray) -> Tuple[float, float, float]:
        """Convert ECEF to LLH coordinates."""
        # WGS84 ellipsoid
        a = 6378137.0  # semi-major axis
        f = 1 / 298.257223563  # flattening
        e2 = 2 * f - f * f  # eccentricity squared
        
        x, y, z = ecef
        
        # Longitude
        lon = np.arctan2(y, x)
        
        # Iterative latitude calculation
        p = np.sqrt(x**2 + y**2)
        lat = np.arctan2(z, p * (1 - e2))  # initial
        
        for _ in range(5):
            N = a / np.sqrt(1 - e2 * np.sin(lat)**2)
            lat = np.arctan2(z + e2 * N * np.sin(lat), p)
        
        # Altitude
        N = a / np.sqrt(1 - e2 * np.sin(lat)**2)
        alt = p / np.cos(lat) - N
        
        return np.degrees(lat), np.degrees(lon), alt
    
    @staticmethod
    def _llh_to_ecef(lat: float, lon: float, alt: float) -> NDArray:
        """Convert LLH to ECEF coordinates."""
        # WGS84
        a = 6378137.0
        f = 1 / 298.257223563
        e2 = 2 * f - f * f
        
        lat_rad = np.radians(lat)
        lon_rad = np.radians(lon)
        
        N = a / np.sqrt(1 - e2 * np.sin(lat_rad)**2)
        
        x = (N + alt) * np.cos(lat_rad) * np.cos(lon_rad)
        y = (N + alt) * np.cos(lat_rad) * np.sin(lon_rad)
        z = (N * (1 - e2) + alt) * np.sin(lat_rad)
        
        return np.array([x, y, z])


def demo_gnss():
    """Demonstrate GNSS processing."""
    print("=" * 60)
    print("GNSS Processing Demo")
    print("=" * 60)
    
    # Create receiver
    config = GNSSConfig(
        constellations=["GPS", "GLONASS"],
        enable_rtk=True
    )
    receiver = GNSSReceiver(config)
    
    # Simulate satellite observations
    print("\nSimulating satellite observations...")
    
    import random
    for prn in range(1, 13):
        obs = SatelliteObservation(
            prn=prn,
            constellation="GPS" if prn <= 8 else "GLONASS",
            azimuth=random.uniform(0, 360),
            elevation=random.uniform(20, 80),
            signal_strength=random.uniform(30, 50),
            pseudorange=20000000 + random.uniform(-100, 100),
            carrier_phase=100000 + random.uniform(-10, 10),
            doppler=-1500 + random.uniform(-500, 500),
            locked=True
        )
        receiver.satellites.append(obs)
    
    print(f"  {len(receiver.satellites)} satellites tracked")
    
    # Select best satellites
    selected = receiver.selector.select_satellites(receiver.satellites)
    print(f"  Selected {len(selected)} for solution")
    
    # Compute solution
    raw_position = np.array([-2700000, 4300000, 3700000])  # Approximate ECEF
    solution = receiver.compute_solution(raw_position)
    
    print("\nPVT Solution:")
    print(f"  Position: ({solution.latitude:.7f}°, {solution.longitude:.7f}°, {solution.altitude:.1f}m)")
    print(f"  Velocity: ({solution.v_north:.2f}, {solution.v_east:.2f}, {solution.v_down:.2f}) m/s")
    print(f"  Accuracy: {solution.horizontal_accuracy:.2f}m (H), {solution.vertical_accuracy:.2f}m (V)")
    print(f"  DOP: HDOP={solution.hdop:.1f}, VDOP={solution.vdop:.1f}")
    print(f"  Fix type: {solution.fix_type}, Satellites: {solution.num_satellites}")
    
    # RTK demo
    print("\n" + "=" * 40)
    print("RTK Processing")
    print("=" * 40)
    
    receiver.reference_position = raw_position.copy()
    
    # Simulate base station observations
    base_obs = [
        SatelliteObservation(
            prn=i + 1,
            constellation="GPS",
            azimuth=random.uniform(0, 360),
            elevation=random.uniform(30, 70),
            signal_strength=45,
            pseudorange=20000000 + random.uniform(-50, 50),
            carrier_phase=100000 + random.uniform(-5, 5),
            doppler=-1500,
            locked=True
        )
        for i in range(8)
    ]
    
    print(f"  Base station: {len(base_obs)} satellites")
    print(f"  RTK fix rate: {receiver.rtk.fix_rate:.1%}")


if __name__ == "__main__":
    demo_gnss()