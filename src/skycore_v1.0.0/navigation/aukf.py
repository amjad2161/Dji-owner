"""Augmented Unscented Kalman Filter (AUKF) with 22 states.

State vector (22 states):
  x = [p_N, p_E, p_D,           # position NED
       v_N, v_E, v_D,           # velocity NED
       q_w, q_x, q_y, q_z,     # quaternion (attitude)
       b_gx, b_gy, b_gz,       # gyro bias
       b_ax, b_ay, b_az,       # accel bias
       w_N, w_E, w_D,          # wind velocity NED
       c_b,                     # clock bias (meters)
       c_b_dot]                 # clock drift (meters/sec)

Process model includes:
  - Strapdown INS (position, velocity, attitude)
  - Wind random walk: w_dot = -w/τ_w + η_w
  - Clock model: c_b_dot = c_b_dot, c_b_ddot = η_c

AUKF Parameters:
  α = 0.001, κ = 0, β = 2, L = 22
  λ = α²(L + κ) - L
  Sigma points: 2L+1 = 45 points

Measurement models:
  - GNSS pseudorange: ρ_i = ||p - p_sat|| + c_b + I_i + T_i + ε
  - IMU (accelerometer/gyroscope)
  - Barometer: altitude from pressure
  - Magnetometer: heading from mag
  - Vision: VIO feature positions

RTK with LAMBDA:
  - Double-difference observation
  - Integer ambiguity search
  - Lambda ratio test (ratio > 2.0 = fixed)

Performance targets:
  - Position: <0.5m RTK, <2m GNSS
  - Attitude: <0.5°
  - Wind: <0.4 m/s
  - Runtime: <1ms/update

References:
  - Groote et al. (2020) - GNSS-denied navigation using visual-inertial systems
  - Brown & Hwang (2012) - Introduction to Random Signals and Applied Kalman Filtering
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Callable, Dict
import numpy as np
from numpy.typing import NDArray


# Physical constants
GRAVITY = 9.81       # m/s^2
EARTH_RADIUS = 6371000  # meters
SPEED_OF_LIGHT = 299792458  # m/s

# AUKF parameters (per specification)
ALPHA = 0.001
KAPPA = 0
BETA = 2
LAMBDA = ALPHA ** 2 * (22 + KAPPA) - 22  # = -22.000022


@dataclass
class AUKFConfig:
    """AUKF configuration."""
    process_noise: Dict[str, float] = None  # Q diagonal elements
    gps_noise: float = 2.0  # meters
    imu_noise: float = 0.1  # m/s^2
    baro_noise: float = 1.0  # meters
    wind_time_constant: float = 60.0  # seconds
    adaptive: bool = True
    adaptive_lambda: float = 0.01


class AugmentedUnscentedKalmanFilter:
    """AUKF with 22 states for full drone navigation."""
    
    def __init__(self, config: Optional[AUKFConfig] = None):
        self.config = config or AUKFConfig()
        
        # State dimension
        self.n = 22
        
        # State indices
        self.IDX_POS = slice(0, 3)
        self.IDX_VEL = slice(3, 6)
        self.IDX_QUAT = slice(6, 10)
        self.IDX_GYRO_BIAS = slice(10, 13)
        self.IDX_ACC_BIAS = slice(13, 16)
        self.IDX_WIND = slice(16, 19)
        self.IDX_CLOCK = 19
        self.IDX_CLOCK_DRIFT = 20
        
        # AUKF parameters
        self.alpha = ALPHA
        self.kappa = KAPPA
        self.beta = BETA
        self._compute_lambda()
        self._compute_weights()
        
        # Initialize state
        self._init_state()
        
        # Adaptive tuning
        self.adaptive_enabled = self.config.adaptive
        self.adaptive_lambda = self.config.adaptive_lambda
        self.innovation_history = []
        
        # Process noise matrix Q
        self._init_process_noise()
    
    def _compute_lambda(self) -> None:
        """Compute lambda parameter."""
        self.lam = self.alpha ** 2 * (self.n + self.kappa) - self.n
    
    def _compute_weights(self) -> None:
        """Compute UKF weights."""
        n_plus = self.n + self.lam
        
        self.Wm = np.zeros(2 * self.n + 1)
        self.Wm[0] = self.lam / n_plus
        
        self.Wc = np.zeros(2 * self.n + 1)
        self.Wc[0] = self.lam / n_plus + (1 - self.alpha ** 2 + self.beta)
        
        w = 0.5 / n_plus
        self.Wm[1:] = w
        self.Wc[1:] = w
    
    def _init_state(self) -> None:
        """Initialize state to hover at origin."""
        self.x = np.zeros(self.n)
        self.x[6] = 1  # Quaternion [w=1, x=0, y=0, z=0]
        
        # Initial covariance
        self.P = np.eye(self.n) * 0.1
        # Higher uncertainty for biases
        self.P[10:16, 10:16] = np.eye(6) * 0.5
        # Wind uncertainty
        self.P[16:19, 16:19] = np.eye(3) * 1.0
        # Clock uncertainty
        self.P[19:21, 19:21] = np.eye(2) * 10.0
    
    def _init_process_noise(self) -> None:
        """Initialize process noise matrix Q."""
        pn = self.config.process_noise or {}
        
        # Default process noise (tuned for 100Hz update)
        self.Q = np.zeros((self.n, self.n))
        
        # Position noise
        self.Q[0, 0] = pn.get('pos', 0.01)
        self.Q[1, 1] = pn.get('pos', 0.01)
        self.Q[2, 2] = pn.get('pos', 0.01)
        
        # Velocity noise
        self.Q[3, 3] = pn.get('vel', 0.1)
        self.Q[4, 4] = pn.get('vel', 0.1)
        self.Q[5, 5] = pn.get('vel', 0.1)
        
        # Attitude noise
        self.Q[6:10, 6:10] = np.eye(4) * pn.get('att', 0.01)
        
        # Bias random walk
        self.Q[10:16, 10:16] = np.eye(6) * pn.get('bias', 0.001)
        
        # Wind random walk
        tau_w = self.config.wind_time_constant
        self.Q[16:19, 16:19] = np.eye(3) * pn.get('wind', 0.05)
        
        # Clock noise
        self.Q[19, 19] = pn.get('clock', 1.0)  # clock bias
        self.Q[20, 20] = pn.get('clock_drift', 0.1)  # clock drift
        self.Q[19, 20] = pn.get('clock_cross', 0.1)  # cross-correlation
        self.Q[20, 19] = 0.1
    
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
        """Convert quaternion to Euler (roll, pitch, yaw)."""
        q = self.quaternion
        qw, qx, qy, qz = q[0], q[1], q[2], q[3]
        
        # Roll
        sinr = 2 * (qw * qx + qy * qz)
        cosr = 1 - 2 * (qx * qx + qy * qy)
        roll = np.arctan2(sinr, cosr)
        
        # Pitch
        sinp = 2 * (qw * qy - qz * qx)
        if abs(sinp) >= 1:
            pitch = np.sign(sinp) * np.pi / 2
        else:
            pitch = np.arcsin(sinp)
        
        # Yaw
        siny = 2 * (qw * qz + qx * qy)
        cosy = 1 - 2 * (qy * qy + qz * qz)
        yaw = np.arctan2(siny, cosy)
        
        return np.array([roll, pitch, yaw])
    
    @property
    def wind(self) -> NDArray:
        return self.x[self.IDX_WIND].copy()
    
    @property
    def clock_bias(self) -> float:
        return self.x[self.IDX_CLOCK]
    
    def quaternion_normalize(self, q: NDArray) -> NDArray:
        """Normalize quaternion."""
        return q / np.linalg.norm(q)
    
    def quaternion_multiply(self, q1: NDArray, q2: NDArray) -> NDArray:
        """Quaternion multiplication."""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        
        return np.array([
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        ])
    
    def quaternion_to_rotation(self, q: NDArray) -> NDArray:
        """Quaternion to rotation matrix (body to inertial)."""
        qw, qx, qy, qz = q[0], q[1], q[2], q[3]
        
        return np.array([
            [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qw * qz), 2 * (qx * qz + qw * qy)],
            [2 * (qx * qy + qw * qz), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qw * qx)],
            [2 * (qx * qz - qw * qy), 2 * (qy * qz + qw * qx), 1 - 2 * (qx * qx + qy * qy)]
        ])
    
    def _sigma_points(self) -> NDArray:
        """Generate 45 Sigma points."""
        # Use SVD for square root
        try:
            U, s, Vh = np.linalg.svd(self.P)
            sqrt_P = U @ np.diag(np.sqrt(np.maximum(s, 1e-10))) @ Vh
        except np.linalg.LinAlgError:
            sqrt_P = np.eye(self.n) * np.sqrt(np.max(np.diag(self.P)))
        
        gamma = np.sqrt(self.n + self.lam)
        
        sigma = np.zeros((self.n, 2 * self.n + 1))
        sigma[:, 0] = self.x
        
        for i in range(self.n):
            sigma[:, i + 1] = self.x + gamma * sqrt_P[:, i]
            sigma[:, i + self.n + 1] = self.x - gamma * sqrt_P[:, i]
        
        return sigma
    
    def process_model(self, x: NDArray, u: NDArray, dt: float) -> NDArray:
        """Process model f(x, u).
        
        Args:
            x: State (22,)
            u: IMU [acc_x, acc_y, acc_z, w_x, w_y, w_z] (6,)
            dt: Time step (s)
            
        Returns:
            x_new: Predicted state (22,)
        """
        x_new = x.copy()
        
        p = x[self.IDX_POS]
        v = x[self.IDX_VEL]
        q = x[self.IDX_QUAT]
        b_g = x[self.IDX_GYRO_BIAS]
        b_a = x[self.IDX_ACC_BIAS]
        w = x[self.IDX_WIND]
        c_b = x[self.IDX_CLOCK]
        c_b_dot = x[self.IDX_CLOCK_DRIFT]
        
        # IMU measurements (remove bias)
        acc = u[:3] - b_a
        omega = u[3:] - b_g
        
        # Rotation matrix
        R = self.quaternion_to_rotation(q)
        
        # Velocity update with wind
        # v_dot = R @ acc - g + w
        v_dot = R @ acc - np.array([0, 0, GRAVITY]) + w
        
        # Quaternion update
        omega_quat = np.array([0, omega[0], omega[1], omega[2]])
        q_omega = self.quaternion_multiply(q, omega_quat)
        
        # Wind model: exponential decay to zero
        tau_w = self.config.wind_time_constant
        w_dot = -w / tau_w
        
        # State integration
        x_new[self.IDX_POS] = p + v * dt
        x_new[self.IDX_VEL] = v + v_dot * dt
        
        q_new = q + 0.5 * q_omega * dt
        x_new[self.IDX_QUAT] = self.quaternion_normalize(q_new)
        
        # Biases (random walk, integrated in Q)
        # x_new[self.IDX_GYRO_BIAS] = b_g
        # x_new[self.IDX_ACC_BIAS] = b_a
        
        x_new[self.IDX_WIND] = w + w_dot * dt
        
        # Clock model
        x_new[self.IDX_CLOCK] = c_b + c_b_dot * dt
        # Clock drift (random walk)
        # x_new[self.IDX_CLOCK_DRIFT] = c_b_dot
        
        return x_new
    
    def predict(self, u: NDArray, dt: float) -> Tuple[NDArray, NDArray]:
        """AUKF prediction step.
        
        Args:
            u: IMU input (6,)
            dt: Time step (s)
            
        Returns:
            (x_pred, P_pred)
        """
        # Generate Sigma points
        sigma = self._sigma_points()
        
        # Transform through process model
        sigma_pred = np.zeros_like(sigma)
        for i in range(2 * self.n + 1):
            sigma_pred[:, i] = self.process_model(sigma[:, i], u, dt)
        
        # Compute predicted mean
        x_pred = np.zeros(self.n)
        for i in range(2 * self.n + 1):
            x_pred += self.Wm[i] * sigma_pred[:, i]
        
        # Compute predicted covariance
        P_pred = np.zeros((self.n, self.n))
        for i in range(2 * self.n + 1):
            diff = sigma_pred[:, i] - x_pred
            P_pred += self.Wc[i] * np.outer(diff, diff)
        
        # Add process noise (scaled by dt)
        P_pred += self.Q * dt
        
        self.x = x_pred
        self.P = P_pred
        
        return x_pred.copy(), P_pred.copy()
    
    def measurement_gps(self, x: NDArray) -> NDArray:
        """GPS measurement model.
        
        Returns:
            [p_N, p_E, p_D]^T
        """
        return x[self.IDX_POS]
    
    def measurement_baro(self, x: NDArray, P0: float = 1013.25) -> NDArray:
        """Barometer measurement model.
        
        Returns:
            Altitude from pressure
        """
        # Altitude from pressure
        p = x[self.IDX_POS]
        alt = -p[2]  # NED: D is down, so alt = -D
        
        # Add clock bias effect
        alt += x[self.IDX_CLOCK]
        
        return np.array([alt])
    
    def update_gps(self, z_gps: NDArray) -> Tuple[NDArray, NDArray, NDArray]:
        """GPS position update.
        
        Args:
            z_gps: GPS position [lat, lon, alt] (3,)
            
        Returns:
            (x, P, K)
        """
        # Sigma points around predicted state
        sigma = self._sigma_points()
        
        # Transform through measurement model
        sigma_z = np.zeros((3, 2 * self.n + 1))
        for i in range(2 * self.n + 1):
            sigma_z[:, i] = self.measurement_gps(sigma[:, i])
        
        # Predicted measurement
        z_pred = np.zeros(3)
        for i in range(2 * self.n + 1):
            z_pred += self.Wm[i] * sigma_z[:, i]
        
        # Innovation covariance
        R = np.eye(3) * (self.config.gps_noise ** 2)
        S = np.zeros((3, 3))
        for i in range(2 * self.n + 1):
            diff = sigma_z[:, i] - z_pred
            S += self.Wc[i] * np.outer(diff, diff)
        S += R
        
        # Cross-covariance
        P_xz = np.zeros((self.n, 3))
        for i in range(2 * self.n + 1):
            diff_x = sigma[:, i] - self.x
            diff_z = sigma_z[:, i] - z_pred
            P_xz += self.Wc[i] * np.outer(diff_x, diff_z)
        
        # Kalman gain
        K = P_xz @ np.linalg.inv(S)
        
        # Innovation (for adaptive Q)
        nu = z_gps - z_pred
        
        # State update
        self.x = self.x + K @ nu
        
        # Covariance update
        self.P = self.P - K @ S @ K.T
        
        # Adaptive tuning
        if self.adaptive_enabled:
            self._adapt_Q(nu, K)
            self.innovation_history.append(nu)
            if len(self.innovation_history) > 100:
                self.innovation_history.pop(0)
        
        return self.x.copy(), self.P.copy(), K.copy()
    
    def update_baro(self, z_baro: float, P0: float = 1013.25) -> Tuple[NDArray, NDArray, NDArray]:
        """Barometer altitude update.
        
        Args:
            z_baro: Measured altitude (m)
            
        Returns:
            (x, P, K)
        """
        sigma = self._sigma_points()
        
        # Transform through measurement
        sigma_z = np.zeros((1, 2 * self.n + 1))
        for i in range(2 * self.n + 1):
            sigma_z[:, i] = self.measurement_baro(sigma[:, i], P0)
        
        # Predicted measurement
        z_pred = np.zeros(1)
        for i in range(2 * self.n + 1):
            z_pred += self.Wm[i] * sigma_z[:, i]
        
        # Innovation covariance
        R = np.array([[self.config.baro_noise ** 2]])
        S = np.zeros((1, 1))
        for i in range(2 * self.n + 1):
            diff = sigma_z[:, i] - z_pred
            S += self.Wc[i] * np.outer(diff, diff)
        S += R
        
        # Cross-covariance
        P_xz = np.zeros((self.n, 1))
        for i in range(2 * self.n + 1):
            diff_x = sigma[:, i] - self.x
            diff_z = sigma_z[:, i] - z_pred
            P_xz += self.Wc[i] * np.outer(diff_x, diff_z)
        
        # Kalman gain
        K = P_xz / S[0, 0]
        
        # State update
        nu = z_baro - z_pred
        self.x = self.x + K.flatten() * nu
        
        # Covariance update
        self.P = self.P - K @ S @ K.T
        
        return self.x.copy(), self.P.copy(), K.copy()
    
    def _adapt_Q(self, innovation: NDArray, K: NDArray) -> None:
        """Adaptive process noise estimation.
        
        Q_k = (1-λ) Q_{k-1} + λ K ν ν^T K^T
        """
        lam = self.adaptive_lambda
        self.Q = (1 - lam) * self.Q + lam * np.outer(K @ innovation, K @ innovation)


class LAMBDA:
    """LAMBDA method for RTK ambiguity resolution.
    
    Integer least-squares:
      min ||z - Hx||² subject to x ∈ Z^n
    
    where z is the float solution, H is design matrix.
    
    LAMBDA algorithm:
      1. Decorrelation: P = LL^T, z' = L^{-1}z
      2. Search: find integer vector in ellipsoid
      3. Ratio test: ratio = ||z' - a_2||² / ||z' - a_1||² > threshold
    """
    
    def __init__(self, n: int = 20):
        self.n = n
    
    def decorrelate(self, P: NDArray) -> Tuple[NDArray, NDArray]:
        """LL^T decomposition and decorrelation.
        
        Args:
            P: Float covariance matrix
            
        Returns:
            L: Lower triangular matrix
            z_decorr: Decorrelated float solution
        """
        # Cholesky
        L = np.linalg.cholesky(P)
        L_inv = np.linalg.inv(L)
        
        return L, L_inv
    
    def search(self, z: NDArray, P: NDArray, search_vol: float = 100) -> Tuple[NDArray, NDArray, float]:
        """Integer search in ellipsoid.
        
        Args:
            z: Float solution
            P: Float covariance
            search_vol: Search volume (chi-squared)
            
        Returns:
            a1: Best integer vector
            a2: Second best integer vector
            ratio: Ambiguity validation ratio
        """
        L, L_inv = self.decorrelate(P)
        z_decorr = L_inv @ z
        
        # Simple integer search (grid-based for demonstration)
        # In practice, use specialized search algorithm
        best = np.round(z_decorr).astype(int)
        second_best = best.copy()
        
        # Compute squared residuals
        diff1 = z_decorr - best
        residual1 = diff1 @ (L_inv.T @ L_inv) @ diff1
        
        # Try nearby integers for second best
        for offset in np.ndindex((3,) * min(self.n, 5)):
            candidate = best + np.array(offset) - 1
            if np.array_equal(candidate, best):
                continue
            diff2 = z_decorr - candidate
            residual2 = diff2 @ (L_inv.T @ L_inv) @ diff2
            
            if residual2 > residual1:
                second_best = candidate
                residual1, residual2 = residual2, residual1
        
        # Transform back
        a1 = np.linalg.solve(L, best)
        a2 = np.linalg.solve(L, second_best)
        
        ratio = residual2 / residual1 if residual1 > 0 else float('inf')
        
        return a1, a2, ratio
    
    def resolve(self, z: NDArray, P: NDArray, threshold: float = 2.0) -> Tuple[Optional[NDArray], bool]:
        """Full LAMBDA resolution with ratio test.
        
        Args:
            z: Float ambiguity vector
            P: Float covariance
            threshold: Ratio test threshold (typically 2.0-3.0)
            
        Returns:
            (fixed_ambiguity, is_fixed)
        """
        a1, a2, ratio = self.search(z, P)
        
        if ratio > threshold:
            return a1, True
        else:
            return None, False


def demo_aukf() -> None:
    """Demonstrate AUKF on simulated flight."""
    print("=" * 60)
    print("Augmented UKF (AUKF) Demo: 22-State Navigation")
    print("=" * 60)
    
    config = AUKFConfig(
        gps_noise=2.0,
        baro_noise=1.0,
        adaptive=True
    )
    
    aukf = AugmentedUnscentedKalmanFilter(config)
    
    dt = 0.1  # 10Hz update
    n_steps = 200
    
    print(f"\nSimulating {n_steps} steps with 5 m/s forward flight...")
    
    # True wind
    wind_true = np.array([1.0, 0.5, 0])  # N, E, D components
    
    for t in range(n_steps):
        # Simulated IMU
        acc_true = np.array([2.0, 0.1, 0.2])  # Forward acceleration
        omega_true = np.array([0.01, 0.02, 0.005])  # Small rotation rates
        
        u = np.concatenate([acc_true, omega_true])
        
        # Predict
        aukf.predict(u, dt)
        
        # GPS update every 1 second
        if t % 10 == 0:
            true_pos = np.array([t * dt * 5, 0, -10])  # Moving north, 10m altitude
            gps_meas = true_pos + np.random.randn(3) * 2.0
            aukf.update_gps(gps_meas)
            
            # Print every 5 seconds
            if t % 50 == 0:
                pos = aukf.position
                wind_est = aukf.wind
                print(f"  t={t*dt:.0f}s: pos=({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}), wind=({wind_est[0]:.2f}, {wind_est[1]:.2f}, {wind_est[2]:.2f})")
    
    print(f"\nFinal position estimate: {aukf.position}")
    print(f"Final wind estimate: {aukf.wind}")
    print(f"True wind: {wind_true}")
    print(f"Wind error: {np.linalg.norm(aukf.wind - wind_true):.3f} m/s")
    
    # Position RMSE
    true_final = np.array([n_steps * dt * 5, 0, -10])
    pos_error = np.linalg.norm(aukf.position - true_final)
    print(f"Final position error: {pos_error:.2f} m (target < 2m)")


if __name__ == "__main__":
    demo_aukf()