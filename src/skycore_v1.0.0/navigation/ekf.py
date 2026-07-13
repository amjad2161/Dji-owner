"""Extended Kalman Filter for 6DOF drone with 16 states.

State vector (16 states):
  x = [p_N, p_E, p_D,           # position (NED)
       v_N, v_E, v_D,           # velocity (NED)
       q_w, q_x, q_y, q_z,     # quaternion (attitude)
       b_gx, b_gy, b_gz,       # gyro bias
       b_ax, b_ay, b_az]       # accel bias

Process model f(x, u):
  p_dot = v
  v_dot = R_b2i * (a - b_a) + g
  q_dot = 0.5 * q ⊗ (ω - b_g)
  b_g_dot = 0
  b_a_dot = 0

Measurement models:
  GPS: h_gps = [p_N, p_E, p_D]^T
  IMU: h_imu = R_i2b * (v_dot - g) + b_a
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple
import numpy as np
from numpy.typing import NDArray


# Constants
GRAVITY = 9.81  # m/s^2
EARTH_ROTATION_RATE = 7.292115e-5  # rad/s


@dataclass
class EKFConfig:
    """EKF configuration for 6DOF drone."""
    initial_state: NDArray  # 16 states
    initial_covariance: NDArray  # 16x16
    process_noise: NDArray  # 16x16 (Q_diagonal)
    gps_noise: float = 2.0  # meters
    imu_noise: float = 0.1  # m/s^2


class ExtendedKalmanFilter:
    """EKF for 6DOF drone navigation with 16 states."""
    
    def __init__(self, config: EKFConfig):
        self.x = config.initial_state.copy()
        self.P = config.initial_covariance.copy()
        self.Q = config.process_noise.copy()
        self.R_gps = config.gps_noise ** 2
        self.R_imu = config.imu_noise ** 2
        
        # State indices
        self.IDX_POS = slice(0, 3)      # p_N, p_E, p_D
        self.IDX_VEL = slice(3, 6)      # v_N, v_E, v_D
        self.IDX_QUAT = slice(6, 10)    # q_w, q_x, q_y, q_z
        self.IDX_GYRO_BIAS = slice(10, 13)  # b_gx, b_gy, b_gz
        self.IDX_ACC_BIAS = slice(13, 16)   # b_ax, b_ay, b_az
    
    @property
    def position(self) -> NDArray:
        return self.x[self.IDX_POS].copy()
    
    @property
    def velocity(self) -> NDArray:
        return self.x[self.IDX_VEL].copy()
    
    @property
    def quaternion(self) -> NDArray:
        return self.x[self.IDX_QUAT].copy()
    
    @property
    def euler_angles(self) -> NDArray:
        """Convert quaternion to Euler angles (roll, pitch, yaw) in radians."""
        q = self.quaternion
        qw, qx, qy, qz = q[0], q[1], q[2], q[3]
        
        # Roll (x-axis rotation)
        sinr_cosp = 2 * (qw * qx + qy * qz)
        cosr_cosp = 1 - 2 * (qx * qx + qy * qy)
        roll = np.arctan2(sinr_cosp, cosr_cosp)
        
        # Pitch (y-axis rotation)
        sinp = 2 * (qw * qy - qz * qx)
        if abs(sinp) >= 1:
            pitch = np.sign(sinp) * np.pi / 2  # use 90 degrees if out of range
        else:
            pitch = np.arcsin(sinp)
        
        # Yaw (z-axis rotation)
        siny_cosp = 2 * (qw * qz + qx * qy)
        cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
        yaw = np.arctan2(siny_cosp, cosy_cosp)
        
        return np.array([roll, pitch, yaw])
    
    def quaternion_normalize(self, q: NDArray) -> NDArray:
        """Normalize quaternion to unit magnitude."""
        return q / np.linalg.norm(q)
    
    def quaternion_multiply(self, q1: NDArray, q2: NDArray) -> NDArray:
        """Quaternion multiplication q = q1 ⊗ q2.
        
        Args:
            q1: First quaternion [w, x, y, z]
            q2: Second quaternion [w, x, y, z]
            
        Returns:
            Product quaternion [w, x, y, z]
        """
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        
        w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
        x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
        y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
        z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        
        return np.array([w, x, y, z])
    
    def quaternion_to_rotation_matrix(self, q: NDArray) -> NDArray:
        """Convert quaternion to rotation matrix (body to inertial).
        
        R_b2i: rotates vectors from body frame to inertial (NED) frame.
        
        Args:
            q: Quaternion [w, x, y, z]
            
        Returns:
            3x3 rotation matrix
        """
        qw, qx, qy, qz = q[0], q[1], q[2], q[3]
        
        # First column
        r00 = 1 - 2 * (qy * qy + qz * qz)
        r10 = 2 * (qx * qy + qw * qz)
        r20 = 2 * (qx * qz - qw * qy)
        
        # Second column
        r01 = 2 * (qx * qy - qw * qz)
        r11 = 1 - 2 * (qx * qx + qz * qz)
        r21 = 2 * (qy * qz + qw * qx)
        
        # Third column
        r02 = 2 * (qx * qz + qw * qy)
        r12 = 2 * (qy * qz - qw * qx)
        r22 = 1 - 2 * (qx * qx + qy * qy)
        
        return np.array([
            [r00, r01, r02],
            [r10, r11, r12],
            [r20, r21, r22]
        ])
    
    def process_model(self, x: NDArray, u: NDArray, dt: float) -> NDArray:
        """Process model f(x, u).
        
        Args:
            x: State vector (16,)
            u: IMU measurements [acc_x, acc_y, acc_z, w_x, w_y, w_z] (6,)
            dt: Time step (s)
            
        Returns:
            x_pred: Predicted state (16,)
        """
        x_new = x.copy()
        
        # Extract components
        p = x[self.IDX_POS]
        v = x[self.IDX_VEL]
        q = x[self.IDX_QUAT]
        b_g = x[self.IDX_GYRO_BIAS]
        b_a = x[self.IDX_ACC_BIAS]
        
        # IMU measurements
        acc_raw = u[:3]  # body frame
        omega_raw = u[3:]  # body frame
        
        # Remove biases
        acc = acc_raw - b_a
        omega = omega_raw - b_g
        
        # Rotation matrix
        R = self.quaternion_to_rotation_matrix(q)
        
        # Gravity in NED (pointing down)
        g_ned = np.array([0, 0, GRAVITY])
        
        # Velocity derivative: v_dot = R * acc - g
        v_dot = R @ acc - g_ned
        
        # Quaternion derivative: q_dot = 0.5 * q ⊗ [0; ω]
        omega_quat = np.array([0, omega[0], omega[1], omega[2]])
        q_omega = self.quaternion_multiply(q, omega_quat)
        
        # Update position: p_new = p + v * dt
        x_new[self.IDX_POS] = p + v * dt
        
        # Update velocity: v_new = v + v_dot * dt
        x_new[self.IDX_VEL] = v + v_dot * dt
        
        # Update quaternion: q_new = q + q_dot * dt
        q_new = q + 0.5 * q_omega * dt
        x_new[self.IDX_QUAT] = self.quaternion_normalize(q_new)
        
        # Biases remain constant (random walk)
        # x_new[self.IDX_GYRO_BIAS] = b_g
        # x_new[self.IDX_ACC_BIAS] = b_a
        
        return x_new
    
    def compute_jacobian_F(self, x: NDArray, u: NDArray, dt: float) -> NDArray:
        """Compute Jacobian of process model w.r.t. state.
        
        F = ∂f/∂x, evaluated at current state.
        
        For efficiency, we compute numerically.
        
        Args:
            x: Current state (16,)
            u: Control input (6,)
            dt: Time step (s)
            
        Returns:
            F: Jacobian matrix (16 x 16)
        """
        n = len(x)
        eps = 1e-6
        
        F = np.zeros((n, n))
        f0 = self.process_model(x, u, dt)
        
        for i in range(n):
            x_eps = x.copy()
            x_eps[i] += eps
            f_eps = self.process_model(x_eps, u, dt)
            F[:, i] = (f_eps - f0) / eps
        
        return F
    
    def measurement_gps(self, x: NDArray) -> NDArray:
        """GPS measurement model h(x).
        
        Returns:
            z_gps = [p_N, p_E, p_D]^T
        """
        return x[self.IDX_POS]
    
    def measurement_jacobian_gps(self, n: int = 16) -> NDArray:
        """Jacobian of GPS measurement.
        
        H_gps = ∂h_gps/∂x
        
        Returns:
            H_gps (3 x 16)
        """
        H = np.zeros((3, n))
        H[0, 0] = 1  # p_N
        H[1, 1] = 1  # p_E
        H[2, 2] = 1  # p_D
        return H
    
    def predict(self, u: NDArray, dt: float) -> Tuple[NDArray, NDArray]:
        """Prediction step.
        
        Args:
            u: IMU input [acc_x, acc_y, acc_z, w_x, w_y, w_z] (6,)
            dt: Time step (s)
            
        Returns:
            (x_pred, P_pred)
        """
        # State prediction
        self.x = self.process_model(self.x, u, dt)
        
        # Jacobian
        F = self.compute_jacobian_F(self.x, u, dt)
        
        # Covariance prediction
        self.P = F @ self.P @ F.T + self.Q * dt
        
        return self.x.copy(), self.P.copy()
    
    def update_gps(self, z_gps: NDArray) -> Tuple[NDArray, NDArray, NDArray]:
        """GPS update step.
        
        Args:
            z_gps: GPS position measurement [lat, lon, alt] (3,)
            
        Returns:
            (x, P, K)
        """
        H = self.measurement_jacobian_gps()
        R = np.eye(3) * self.R_gps
        
        # Innovation
        z_pred = self.measurement_gps(self.x)
        nu = z_gps - z_pred
        
        # Innovation covariance
        S = H @ self.P @ H.T + R
        
        # Kalman gain
        K = self.P @ H.T @ np.linalg.inv(S)
        
        # State update
        self.x = self.x + K @ nu
        
        # Covariance update (Joseph form)
        I_KH = np.eye(16) - K @ H
        self.P = I_KH @ self.P @ I_KH.T + K @ R @ K.T
        
        return self.x.copy(), self.P.copy(), K.copy()
    
    def update_imu(self, z_imu: NDArray) -> Tuple[NDArray, NDArray, NDArray]:
        """IMU update (accelerometer).
        
        Args:
            z_imu: Measured acceleration in body frame (3,)
            
        Returns:
            (x, P, K)
        """
        # IMU measurement model: z_imu = R_i2b * (v_dot - g) + b_a + noise
        # This is nonlinear - we use the current state to compute expected measurement
        
        R = self.quaternion_to_rotation_matrix(self.x[self.IDX_QUAT])
        R_i2b = R.T  # Inverse rotation
        
        g_ned = np.array([0, 0, GRAVITY])
        v = self.x[self.IDX_VEL]
        
        # Predicted acceleration in body frame
        v_dot = (R @ z_imu - g_ned)
        accel_pred = R_i2b @ v_dot + self.x[self.IDX_ACC_BIAS]
        
        # Innovation
        nu = z_imu - accel_pred
        
        # For simplicity, use identity Jacobian for IMU
        H = np.zeros((3, 16))
        H[:, 3:6] = np.eye(3)  # Velocity component
        
        R_imu = np.eye(3) * self.R_imu
        
        # Innovation covariance
        S = H @ self.P @ H.T + R_imu
        
        # Kalman gain
        K = self.P @ H.T @ np.linalg.inv(S)
        
        # State update
        self.x = self.x + K @ nu
        
        # Covariance update
        I_KH = np.eye(16) - K @ H
        self.P = I_KH @ self.P @ I_KH.T + K @ R_imu @ K.T
        
        return self.x.copy(), self.P.copy(), K.copy()
    
    def reset(self, x0: NDArray, P0: NDArray) -> None:
        """Reset filter to initial state."""
        self.x = x0.copy()
        self.P = P0.copy()


def demo_ekf() -> None:
    """Demonstrate EKF on simulated drone flight."""
    print("=" * 60)
    print("Extended Kalman Filter Demo: 6DOF Drone")
    print("=" * 60)
    
    # Initial state (hover at origin)
    x0 = np.zeros(16)
    x0[6] = 1  # quaternion [w=1, x=0, y=0, z=0] = no rotation
    
    # Initial covariance (high uncertainty in biases)
    P0 = np.eye(16) * 0.1
    P0[10:16, 10:16] = np.eye(6) * 0.5  # Higher bias uncertainty
    
    # Process noise
    Q = np.zeros((16, 16))
    Q[0:3, 0:3] = np.eye(3) * 0.01   # Position noise
    Q[3:6, 3:6] = np.eye(3) * 0.1    # Velocity noise
    Q[6:10, 6:10] = np.eye(4) * 0.01  # Quaternion noise
    Q[10:16, 10:16] = np.eye(6) * 0.001  # Bias random walk
    
    config = EKFConfig(
        initial_state=x0,
        initial_covariance=P0,
        process_noise=Q,
        gps_noise=2.0,
        imu_noise=0.1
    )
    
    ekf = ExtendedKalmanFilter(config)
    
    # Simulate constant forward flight
    dt = 0.1
    n_steps = 100
    
    print(f"\nSimulating {n_steps} steps of forward flight at 5 m/s...")
    
    for t in range(n_steps):
        # True acceleration (2 m/s² forward)
        acc_true = np.array([2.0, 0, 0])
        omega_true = np.array([0, 0, 0])
        
        # Noisy IMU measurement
        acc_meas = acc_true + np.random.randn(3) * 0.1
        omega_meas = omega_true + np.random.randn(3) * 0.01
        
        u = np.concatenate([acc_meas, omega_meas])
        
        # Predict
        ekf.predict(u, dt)
        
        # Every 20 steps, update with GPS
        if t % 20 == 0:
            true_pos = np.array([t * dt * 5, 0, 0])  # 5 m/s forward
            gps_meas = true_pos + np.random.randn(3) * 2.0  # 2m GPS noise
            ekf.update_gps(gps_meas)
            
            print(f"  Step {t:3d}: pos=({ekf.position[0]:.1f}, {ekf.position[1]:.1f}, {ekf.position[2]:.1f})")
    
    print(f"\nFinal estimated position: {ekf.position}")
    print(f"Final estimated velocity: {ekf.velocity}")
    print(f"Final estimated euler (deg): {np.radegdeg(ekf.euler_angles)}")


if __name__ == "__main__":
    demo_ekf()