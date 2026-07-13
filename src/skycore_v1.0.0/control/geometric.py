"""Geometric Controller on SE(3) for attitude control.

Implements geometric quaternion control on the special Euclidean group SE(3).

Attitude error on SO(3):
  e_R = 0.5 * vee(R_des^T @ R - R^T @ R_des)

  where vee() maps 3x3 skew-symmetric matrix to 3-vector

Angular velocity error:
  e_omega = omega - R^T @ R_des @ omega_des

Control law (from Lee et al. "Geometric Control of Quadrotors"):
  tau = -k_R @ e_R - k_omega @ e_omega + omega_cross @ J @ omega + J @ omega_dot_des

Position controller (outer loop):
  a_cmd = -K_p @ (p - p_d) - K_d @ (v - v_d) + v_dot_d + g - w_est

Desired quaternion from thrust and yaw:
  R_des = [thrust_dir | yaw_cross | yaw_dir]

References:
  - Lee et al. (2015) - Geometric Control of Quadrotors
  - Bullo & Lewis (2004) - Geometric Control of Mechanical Systems
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
from numpy.typing import NDArray


@dataclass
class GeometricControlConfig:
    """Geometric controller configuration."""
    # Attitude gains
    k_R: float = 1.0   # Attitude error gain
    k_omega: float = 0.5  # Angular velocity error gain
    
    # Position gains
    K_p: float = 1.0   # Position error gain
    K_d: float = 0.5   # Velocity error gain
    
    # Inertia matrix (quadrotor)
    J: Optional[NDArray] = None
    
    # Max thrust (N)
    max_thrust: float = 20.0
    
    # Max angular velocity (rad/s)
    max_omega: float = 10.0
    
    # Gravity
    g: float = 9.81


class GeometricController:
    """Geometric controller for quadrotor on SE(3)."""
    
    def __init__(self, config: Optional[GeometricControlConfig] = None):
        self.config = config or GeometricControlConfig()
        
        # Inertia (default quadrotor ~0.1 kg m^2)
        if self.config.J is None:
            self.J = np.diag([0.1, 0.1, 0.1])
        else:
            self.J = self.config.J
        
        # Gains
        self.k_R = self.config.k_R
        self.k_omega = self.config.k_omega
        self.K_p = self.config.K_p
        self.K_d = self.config.K_d
        
        # State
        self._initialized = False
    
    @staticmethod
    def skew_symmetric(v: NDArray) -> NDArray:
        """Create skew-symmetric matrix from 3-vector.
        
        Args:
            v: [v_x, v_y, v_z]
            
        Returns:
            Skew-symmetric matrix [[ 0, -v_z,  v_y],
                                   [ v_z,  0, -v_x],
                                   [-v_y,  v_x,  0]]
        """
        return np.array([
            [0, -v[2], v[1]],
            [v[2], 0, -v[0]],
            [-v[1], v[0], 0]
        ])
    
    @staticmethod
    def vee(S: NDArray) -> NDArray:
        """Inverse of skew(): extract vector from skew-symmetric matrix.
        
        Args:
            S: Skew-symmetric 3x3 matrix
            
        Returns:
            v: Corresponding 3-vector
        """
        return np.array([S[2, 1], S[0, 2], S[1, 0]])
    
    @staticmethod
    def quaternion_to_rotation(q: NDArray) -> NDArray:
        """Convert quaternion [w, x, y, z] to rotation matrix."""
        w, x, y, z = q
        
        return np.array([
            [1 - 2*(y**2 + z**2), 2*(x*y - w*z), 2*(x*z + w*y)],
            [2*(x*y + w*z), 1 - 2*(x**2 + z**2), 2*(y*z - w*x)],
            [2*(x*z - w*y), 2*(y*z + w*x), 1 - 2*(x**2 + y**2)]
        ])
    
    @staticmethod
    def quaternion_normalize(q: NDArray) -> NDArray:
        """Normalize quaternion."""
        return q / np.linalg.norm(q)
    
    @staticmethod
    def rotation_to_quaternion(R: NDArray) -> NDArray:
        """Convert rotation matrix to quaternion [w, x, y, z].
        
        Uses trace method with numerical stability.
        """
        trace = np.trace(R)
        
        if trace > 0:
            s = 0.5 / np.sqrt(trace + 1.0)
            w = 0.25 / s
            x = (R[2, 1] - R[1, 2]) * s
            y = (R[0, 2] - R[2, 0]) * s
            z = (R[1, 0] - R[0, 1]) * s
        elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
            s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
            w = (R[2, 1] - R[1, 2]) / s
            x = 0.25 * s
            y = (R[0, 1] + R[1, 0]) / s
            z = (R[0, 2] + R[2, 0]) / s
        elif R[1, 1] > R[2, 2]:
            s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
            w = (R[0, 2] - R[2, 0]) / s
            x = (R[0, 1] + R[1, 0]) / s
            y = 0.25 * s
            z = (R[1, 2] + R[2, 1]) / s
        else:
            s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
            w = (R[1, 0] - R[0, 1]) / s
            x = (R[0, 2] + R[2, 0]) / s
            y = (R[1, 2] + R[2, 1]) / s
            z = 0.25 * s
        
        return np.array([w, x, y, z])
    
    @staticmethod
    def quaternion_derivative(q: NDArray, omega: NDArray) -> NDArray:
        """Compute quaternion time derivative.
        
        Args:
            q: Quaternion [w, x, y, z]
            omega: Angular velocity [wx, wy, wz]
            
        Returns:
            q_dot: Quaternion derivative
        """
        w, x, y, z = q
        
        return 0.5 * np.array([
            -x * omega[0] - y * omega[1] - z * omega[2],
             w * omega[0] + y * omega[2] - z * omega[1],
             w * omega[1] - x * omega[2] + z * omega[0],
             w * omega[2] + x * omega[1] - y * omega[0]
        ])
    
    def compute_attitude_error(self, R: NDArray, R_des: NDArray) -> Tuple[NDArray, NDArray]:
        """Compute attitude error on SO(3).
        
        Args:
            R: Current rotation matrix (3x3)
            R_des: Desired rotation matrix (3x3)
            
        Returns:
            (e_R, e_omega): Attitude error vector and angular velocity error
        """
        # Attitude error via geodesic distance
        # e_R = 0.5 * vee(R_des^T @ R - R^T @ R_des)
        S_error = R_des.T @ R - R.T @ R_des
        e_R = 0.5 * self.vee(S_error)
        
        return e_R, np.zeros(3)  # e_omega computed separately
    
    def compute_thrust_direction(
        self,
        a_cmd: NDArray,
        yaw_des: float
    ) -> Tuple[NDArray, float]:
        """Compute desired rotation from commanded acceleration and yaw.
        
        Args:
            a_cmd: Commanded acceleration [ax, ay, az] in NED
            yaw_des: Desired yaw angle (rad)
            
        Returns:
            (R_des, thrust): Desired rotation matrix and thrust magnitude
        """
        # Thrust direction (normalize to get direction)
        thrust_dir = a_cmd.copy()
        thrust_mag = np.linalg.norm(thrust_dir)
        
        if thrust_mag < 1e-6:
            thrust_dir = np.array([0, 0, -1])  # Default to hover
            thrust_mag = self.config.g
        else:
            thrust_dir = thrust_dir / thrust_mag
        
        # Yaw direction in NED
        cy = np.cos(yaw_des)
        sy = np.sin(yaw_des)
        yaw_dir = np.array([cy, sy, 0])
        
        # Corrected yaw direction (orthogonal to thrust)
        # If thrust is nearly vertical, use default yaw
        if abs(thrust_dir[2]) > 0.99:
            yaw_dir = np.array([1, 0, 0])
        
        # Third direction (right direction from cross product)
        right_dir = np.cross(thrust_dir, yaw_dir)
        right_dir = right_dir / np.linalg.norm(right_dir)
        
        # Recompute yaw direction for orthogonality
        yaw_dir = np.cross(right_dir, thrust_dir)
        
        # Build rotation matrix [b1 | b2 | b3]
        # b1 (thrust), b2 (right), b3 (forward)
        R_des = np.column_stack([right_dir, yaw_dir, thrust_dir])
        
        return R_des, thrust_mag
    
    def compute_attitude_control(
        self,
        R: NDArray,
        omega: NDArray,
        R_des: NDArray,
        omega_des: Optional[NDArray] = None,
        omega_dot_des: Optional[NDArray] = None
    ) -> Tuple[float, NDArray]:
        """Compute attitude control torque.
        
        Args:
            R: Current rotation matrix (3x3)
            omega: Current angular velocity (3,)
            R_des: Desired rotation matrix (3x3)
            omega_des: Desired angular velocity (3,) - optional
            omega_dot_des: Desired angular acceleration (3,) - optional
            
        Returns:
            (thrust, tau): Thrust magnitude and torque vector
        """
        if omega_des is None:
            omega_des = np.zeros(3)
        if omega_dot_des is None:
            omega_dot_des = np.zeros(3)
        
        # Compute attitude error
        e_R, _ = self.compute_attitude_error(R, R_des)
        
        # Angular velocity error
        e_omega = omega - R.T @ R_des @ omega_des
        
        # Gyroscopic compensation: omega_cross @ J @ omega
        omega_cross = self.skew_symmetric(omega)
        gyro_comp = omega_cross @ self.J @ omega
        
        # Control law: tau = -k_R * e_R - k_omega * e_omega + gyro_comp + J * omega_dot_des
        tau = -self.k_R * e_R - self.k_omega * e_omega + gyro_comp + self.J @ omega_dot_des
        
        # Thrust (simplified: vertical in body frame)
        thrust = self.config.g  # Assume hovering for now
        
        return thrust, tau
    
    def compute_position_control(
        self,
        p: NDArray,
        v: NDArray,
        p_des: NDArray,
        v_des: NDArray,
        v_dot_des: NDArray,
        yaw_des: float,
        w_est: Optional[NDArray] = None
    ) -> Tuple[NDArray, NDArray]:
        """Compute position control (outer loop).
        
        Args:
            p: Current position [p_N, p_E, p_D] (3,)
            v: Current velocity [v_N, v_E, v_D] (3,)
            p_des: Desired position
            v_des: Desired velocity
            v_dot_des: Desired acceleration
            yaw_des: Desired yaw angle
            w_est: Estimated wind velocity (optional)
            
        Returns:
            (a_cmd, R_des): Commanded acceleration and desired rotation
        """
        if w_est is None:
            w_est = np.zeros(3)
        
        # Position error
        p_error = p_des - p
        v_error = v_des - v
        
        # Commanded acceleration (PD + feedforward + gravity + wind compensation)
        a_cmd = (
            -self.K_p * p_error
            - self.K_d * v_error
            + v_dot_des
            + np.array([0, 0, self.config.g])
            - w_est
        )
        
        # Compute desired rotation from acceleration
        R_des, thrust = self.compute_thrust_direction(a_cmd, yaw_des)
        
        return a_cmd, R_des
    
    def step(
        self,
        p: NDArray,
        v: NDArray,
        q: NDArray,
        omega: NDArray,
        p_des: NDArray,
        v_des: NDArray,
        v_dot_des: NDArray,
        yaw_des: float,
        w_est: Optional[NDArray] = None
    ) -> Tuple[float, NDArray]:
        """Full geometric control step.
        
        Args:
            p: Current position
            v: Current velocity
            q: Current quaternion [w, x, y, z]
            omega: Current angular velocity
            p_des: Desired position
            v_des: Desired velocity
            v_dot_des: Desired acceleration
            yaw_des: Desired yaw
            w_est: Wind estimate
            
        Returns:
            (thrust, tau): Motor outputs [thrust, roll, pitch, yaw]
        """
        # Position control (outer loop)
        a_cmd, R_des = self.compute_position_control(
            p, v, p_des, v_des, v_dot_des, yaw_des, w_est
        )
        
        # Current rotation matrix
        R = self.quaternion_to_rotation(q)
        
        # Attitude control (inner loop)
        thrust, tau = self.compute_attitude_control(R, omega, R_des)
        
        # Clamp thrust
        thrust = np.clip(thrust, 0, self.config.max_thrust)
        
        return thrust, tau
    
    def attitude_step(
        self,
        q: NDArray,
        omega: NDArray,
        R_des: NDArray,
        omega_des: Optional[NDArray] = None
    ) -> Tuple[float, NDArray]:
        """Attitude-only control step.
        
        Args:
            q: Current quaternion
            omega: Current angular velocity
            R_des: Desired rotation matrix
            omega_des: Desired angular velocity
            
        Returns:
            (thrust, tau): Motor outputs
        """
        R = self.quaternion_to_rotation(q)
        thrust = self.config.g  # Hover thrust
        
        _, tau = self.compute_attitude_control(R, omega, R_des, omega_des)
        
        return thrust, tau


def demo_geometric_control():
    """Demonstrate geometric controller."""
    print("=" * 60)
    print("Geometric Controller Demo")
    print("=" * 60)
    
    config = GeometricControlConfig(
        k_R=1.0,
        k_omega=0.5,
        K_p=1.0,
        K_d=0.5,
        J=np.diag([0.1, 0.1, 0.1])
    )
    
    ctrl = GeometricController(config)
    
    # Initial state: hover
    p = np.array([0, 0, 0])
    v = np.array([0, 0, 0])
    q = np.array([1, 0, 0, 0])  # Identity quaternion
    omega = np.array([0, 0, 0])
    
    # Desired: move to (10, 5, -20)
    p_des = np.array([10, 5, -20])
    v_des = np.zeros(3)
    v_dot_des = np.zeros(3)
    yaw_des = 0
    
    print("\nControlling from (0,0,0) to (10,5,-20)...")
    
    dt = 0.01
    for t in range(500):
        # Compute control
        thrust, tau = ctrl.step(
            p, v, q, omega,
            p_des, v_des, v_dot_des, yaw_des
        )
        
        # Simple dynamics (no inertia model)
        # Update velocity and position
        R = ctrl.quaternion_to_rotation(q)
        
        # Acceleration in inertial frame
        a = -np.array([0, 0, ctrl.config.g]) + R[:, 2] * thrust / 0.5  # mass = 0.5 kg
        
        # Integrate
        v = v + a * dt
        p = p + v * dt
        
        # Quaternion integration
        q = ctrl.quaternion_normalize(q + ctrl.quaternion_derivative(q, omega) * dt)
        
        if t % 100 == 0:
            print(f"  t={t*dt:.1f}s: pos=({p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f}), "
                  f"thrust={thrust:.1f}N, tau=({tau[0]:.2f}, {tau[1]:.2f}, {tau[2]:.2f})")
    
    print(f"\nFinal position: {p}")
    print(f"Error: {np.linalg.norm(p - p_des):.2f}m")


if __name__ == "__main__":
    demo_geometric_control()