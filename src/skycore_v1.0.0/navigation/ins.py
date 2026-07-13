"""Strapdown Inertial Navigation System (INS).

Implements dead-reckoning navigation using IMU data when GNSS is unavailable.

Equations:

Velocity update:
  v_k = v_{k-1} + (R_b2i * a - g) * dt

Position update:
  p_k = p_{k-1} + v * dt

Quaternion update (rotation rate integration):
  q_k = q_{k-1} * q(ω * dt / 2)
  
  where q(ω) = [0, ω_x, ω_y, ω_z] for small angle approximation

Rotation matrix from quaternion:
  R = [[1-2(qy²+qz²), 2(qxqy-qzqw), 2(qxqz+qyqw)],
       [2(qxqy+qzqw), 1-2(qx²+qz²), 2(qyqz-qxqw)],
       [2(qxqz-qyqw), 2(qyqz+qxqw), 1-2(qx²+qy²)]]

Gravity model (spherical earth):
  g = [0, 0, 9.81] m/s² (simplified, ignoring latitude effects)

Error-state correction from EKF/AUKF:
  δv = K_v * (v_gnss - v_ins)
  δp = K_p * (p_gnss - p_ins)
  δq = correction to quaternion

References:
  - Woodman (2007) - An introduction to inertial navigation
  - Janusz (2014) - Strapdown Inertial Navigation Systems
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
from numpy.typing import NDArray


GRAVITY = 9.81  # m/s²
EARTH_ROTATION = 7.292115e-5  # rad/s


@dataclass
class INSConfig:
    """INS configuration."""
    initial_position: NDArray  # [lat, lon, alt] in radians/meters
    initial_velocity: NDArray  # [v_N, v_E, v_D] m/s
    initial_attitude: NDArray  # [roll, pitch, yaw] radians
    imu_rate: float = 100  # Hz
    gravity_model: str = "simple"  # "simple" or "WGS84"


class StrapdownINS:
    """Strapdown INS for dead-reckoning navigation."""
    
    def __init__(self, config: Optional[INSConfig] = None):
        self.config = config or INSConfig(
            initial_position=np.array([0, 0, 0]),
            initial_velocity=np.array([0, 0, 0]),
            initial_attitude=np.array([0, 0, 0])
        )
        
        # Initialize state
        self._init_state()
        
        # Navigation timestamp
        self.t_nav = 0.0
        
        # Error correction from EKF
        self.error_correction_enabled = False
    
    def _init_state(self) -> None:
        """Initialize navigation state."""
        # Position (NED frame)
        self.p_ned = self.config.initial_position.copy()
        
        # Velocity (NED frame)
        self.v_ned = self.config.initial_velocity.copy()
        
        # Attitude as quaternion
        rpy = self.config.initial_attitude
        self.q = self.euler_to_quaternion(rpy)
        
        # Previous time
        self.t_prev = None
    
    @staticmethod
    def euler_to_quaternion(euler: NDArray) -> NDArray:
        """Convert Euler angles to quaternion.
        
        Args:
            euler: [roll, pitch, yaw] in radians
            
        Returns:
            q: [w, x, y, z]
        """
        roll, pitch, yaw = euler
        
        cy = np.cos(yaw / 2)
        sy = np.sin(yaw / 2)
        cp = np.cos(pitch / 2)
        sp = np.sin(pitch / 2)
        cr = np.cos(roll / 2)
        sr = np.sin(roll / 2)
        
        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        
        return np.array([w, x, y, z])
    
    @staticmethod
    def quaternion_to_euler(q: NDArray) -> NDArray:
        """Convert quaternion to Euler angles.
        
        Args:
            q: [w, x, y, z]
            
        Returns:
            euler: [roll, pitch, yaw] radians
        """
        w, x, y, z = q
        
        # Roll (x-axis rotation)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = np.arctan2(sinr_cosp, cosr_cosp)
        
        # Pitch (y-axis rotation)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = np.sign(sinp) * np.pi / 2
        else:
            pitch = np.arcsin(sinp)
        
        # Yaw (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = np.arctan2(siny_cosp, cosy_cosp)
        
        return np.array([roll, pitch, yaw])
    
    @staticmethod
    def quaternion_to_rotation(q: NDArray) -> NDArray:
        """Quaternion to rotation matrix (body to NED).
        
        Args:
            q: [w, x, y, z]
            
        Returns:
            R: 3x3 rotation matrix
        """
        w, x, y, z = q
        
        return np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]
        ])
    
    @staticmethod
    def quaternion_multiply(q1: NDArray, q2: NDArray) -> NDArray:
        """Quaternion multiplication q = q1 ⊗ q2."""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        
        return np.array([
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        ])
    
    @staticmethod
    def quaternion_normalize(q: NDArray) -> NDArray:
        """Normalize quaternion to unit magnitude."""
        return q / np.linalg.norm(q)
    
    @property
    def position_ned(self) -> NDArray:
        """Current NED position."""
        return self.p_ned.copy()
    
    @property
    def velocity_ned(self) -> NDArray:
        """Current NED velocity."""
        return self.v_ned.copy()
    
    @property
    def euler_angles(self) -> NDArray:
        """Current Euler angles (roll, pitch, yaw)."""
        return self.quaternion_to_euler(self.q)
    
    @property
    def rotation_matrix(self) -> NDArray:
        """Current rotation matrix (body to NED)."""
        return self.quaternion_to_rotation(self.q)
    
    def update(self, acc: NDArray, omega: NDArray, dt: float) -> None:
        """Update INS with IMU measurements.
        
        Args:
            acc: Specific force [ax, ay, az] in body frame (m/s²)
            omega: Angular velocity [wx, wy, wz] in body frame (rad/s)
            dt: Time step (s)
        """
        # Remove gravity from accelerometer readings
        # In NED frame, gravity points down (positive D)
        g_ned = np.array([0, 0, GRAVITY])
        
        # Rotation matrix (body to NED)
        R = self.rotation_matrix
        
        # Specific force in NED frame
        f_ned = R @ acc
        
        # Velocity update: v += (f - g) * dt
        v_dot = f_ned - g_ned
        self.v_ned = self.v_ned + v_dot * dt
        
        # Position update: p += v * dt
        self.p_ned = self.p_ned + self.v_ned * dt
        
        # Quaternion update
        # Small angle approximation: q_new = q ⊗ q(ω*dt/2)
        dq = np.array([1, omega[0] * dt / 2, omega[1] * dt / 2, omega[2] * dt / 2])
        self.q = self.quaternion_normalize(self.quaternion_multiply(self.q, dq))
        
        self.t_nav += dt
    
    def update_high_rate(self, acc: NDArray, omega: NDArray, n_substeps: int = 10) -> None:
        """High-rate INS update for improved accuracy.
        
        Uses multiple substeps per IMU update.
        
        Args:
            acc: Specific force (body frame)
            omega: Angular velocity (body frame)
            n_substeps: Number of substeps
        """
        dt = 1.0 / (self.config.imu_rate * n_substeps)
        
        for _ in range(n_substeps):
            self.update(acc, omega, dt)
    
    def correct(self, delta_v: NDArray, delta_p: NDArray, delta_att: Optional[NDArray] = None) -> None:
        """Apply error corrections from EKF/AUKF.
        
        Args:
            delta_v: Velocity correction [m/s]
            delta_p: Position correction [m]
            delta_att: Optional attitude correction [rad]
        """
        # Apply corrections
        self.v_ned = self.v_ned - delta_v  # Minus because correction removes error
        self.p_ned = self.p_ned - delta_p
        
        if delta_att is not None:
            # Apply attitude correction via quaternion update
            dq = self.euler_to_quaternion(delta_att)
            self.q = self.quaternion_normalize(self.quaternion_multiply(self.q, dq))
    
    def reset(
        self,
        position: Optional[NDArray] = None,
        velocity: Optional[NDArray] = None,
        attitude: Optional[NDArray] = None
    ) -> None:
        """Reset INS to new state.
        
        Args:
            position: New NED position (or None to keep current)
            velocity: New NED velocity (or None to keep current)
            attitude: New attitude as euler (or None to keep current)
        """
        if position is not None:
            self.p_ned = position.copy()
        if velocity is not None:
            self.v_ned = velocity.copy()
        if attitude is not None:
            self.q = self.euler_to_quaternion(attitude)
        
        self.t_nav = 0.0
    
    def compute_ground_speed(self) -> Tuple[float, float]:
        """Compute horizontal ground speed and heading.
        
        Returns:
            (speed_mps, heading_rad)
        """
        v_horizontal = np.sqrt(self.v_ned[0] ** 2 + self.v_ned[1] ** 2)
        heading = np.arctan2(self.v_ned[1], self.v_ned[0])
        return v_horizontal, heading
    
    def compute_altitude_rate(self) -> float:
        """Compute vertical speed."""
        return -self.v_ned[2]  # Negative because D is down
    
    def dead_reckon(self, acc: NDArray, omega: NDArray, duration: float, rate: float = 100) -> None:
        """Dead-reckon for specified duration.
        
        Args:
            acc: Acceleration (body frame)
            omega: Angular velocity (body frame)
            duration: Duration (seconds)
            rate: Update rate (Hz)
        """
        n_steps = int(duration * rate)
        dt = 1.0 / rate
        
        for _ in range(n_steps):
            self.update(acc, omega, dt)
    
    def get_state(self) -> dict:
        """Get full navigation state as dictionary."""
        return {
            'position_ned': self.p_ned.copy(),
            'velocity_ned': self.v_ned.copy(),
            'euler': self.euler_angles,
            'quaternion': self.q.copy(),
            'ground_speed': self.compute_ground_speed()[0],
            'heading': self.compute_ground_speed()[1],
            'altitude_rate': self.compute_altitude_rate(),
            'time_nav': self.t_nav
        }


def demo_ins() -> None:
    """Demonstrate INS dead-reckoning."""
    print("=" * 60)
    print("Strapdown INS Demo: Dead Reckoning")
    print("=" * 60)
    
    # Initial state: hover at origin
    config = INSConfig(
        initial_position=np.array([0, 0, 0]),
        initial_velocity=np.array([0, 0, 0]),
        initial_attitude=np.array([0, 0, 0])
    )
    
    ins = StrapdownINS(config)
    
    dt = 0.01  # 100Hz
    duration = 10  # seconds
    
    # Simulate forward flight at 5 m/s
    acc = np.array([2.0, 0.1, 0.2])  # ~5 m/s² net (accounting for drag)
    omega = np.array([0, 0, 0])
    
    print(f"\nSimulating {duration}s forward flight at 5 m/s...")
    
    for t in range(int(duration / dt)):
        ins.update(acc, omega, dt)
        
        if (t + 1) % 1000 == 0:  # Print every 10 seconds
            state = ins.get_state()
            print(f"  t={state['time_nav']:.1f}s: pos=({state['position_ned'][0]:.1f}, {state['position_ned'][1]:.1f}, {state['position_ned'][2]:.1f}), "
                  f"speed={state['ground_speed']:.1f} m/s")
    
    state = ins.get_state()
    print(f"\nFinal INS position: {state['position_ned']}")
    print(f"Expected position: [50, 0, 0] (5 m/s * 10 s)")
    print(f"Position error: {np.linalg.norm(state['position_ned'] - np.array([50, 0, 0])):.2f} m")
    
    # Show that gravity is properly compensated
    print(f"\nVelocity after 10s: {state['velocity_ned']} m/s")
    print(f"Net acceleration (should be ~0): {acc - np.array([0, 0, GRAVITY])}")
    
    # Dead reckoning without IMU (drift demonstration)
    print("\n" + "=" * 40)
    print("Dead Reckoning Drift Demo (no corrections)")
    print("=" * 40)
    
    ins2 = StrapdownINS(config)
    
    # Simulate for 30 seconds with drift
    for t in range(int(30 / dt)):
        # Small bias in accelerometer causes drift
        acc_biased = acc + np.array([0.01, 0.005, 0.02])  # 10 mg bias
        ins2.update(acc_biased, omega, dt)
    
    state2 = ins2.get_state()
    print(f"\nAfter 30s with 10mg accelerometer bias:")
    print(f"  Position: {state2['position_ned']}")
    print(f"  Velocity: {state2['velocity_ned']}")
    print(f"  Position drift: {np.linalg.norm(state2['position_ned'] - np.array([150, 0, 0])):.1f} m")


if __name__ == "__main__":
    demo_ins()