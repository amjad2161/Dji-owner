"""
SkyCore 22-State Adaptive Unscented Kalman Filter (AUKF)
========================================================
Adaptive Kalman filter with multiple models for robust navigation.
"""

import numpy as np
from typing import Dict, Tuple, List
import logging

log = logging.getLogger(__name__)


class AdaptiveUKF:
    """
    22-State Adaptive Unscented Kalman Filter.
    
    State vector (22 dimensions):
    [0-2]   Position (x, y, z)
    [3-5]   Velocity (vx, vy, vz)
    [6-9]   Quaternion (qw, qx, qy, qz)
    [10-12] Gyro bias (bx, by, bz)
    [13-15] Accel bias (ax, ay, az)
    [16-18] Wind velocity (wx, wy, wz)
    [19]    Baro bias
    [20]    GPS L1 bias
    [21]    Magnetic declination
    
    Adaptive features:
    - Multiple model switching
    - Innovation-based adaptation
    - Noise adaptive estimation
    """
    
    def __init__(self, lambda_param: float = 3.0, n_sigma: int = 45):
        """
        Initialize AUKF.
        
        Args:
            lambda_param: Adaptation gain
            n_sigma: Number of sigma points
        """
        self.dim_x = 22
        self.dim_z = 6  # GPS + barometer
        
        self.lambda_param = lambda_param
        self.n_sigma = n_sigma
        
        # State estimate
        self.x = np.zeros(self.dim_x)
        
        # Error covariance
        self.P = np.eye(self.dim_x) * 10
        
        # Process noise (adaptive)
        self.Q = np.eye(self.dim_x) * 0.01
        
        # Measurement noise (adaptive)
        self.R = np.eye(self.dim_z)
        
        # Adaptive weights
        self.model_weights = np.ones(3) / 3  # 3 models
        self.model_probs = np.ones(3) / 3
        
        # Models: [normal, degraded_gps, high_maneuvers]
        self.model_Q = [
            np.eye(self.dim_x) * 0.01,
            np.eye(self.dim_x) * 0.1,
            np.eye(self.dim_x) * 0.05
        ]
        
        # Innovation history for adaptation
        self.innovation_history = []
        self.max_history = 100
        
        # Sigma point parameters
        self.alpha = 0.001
        self.beta = 2.0
        self.kappa = 0.0
        self.lam = self.alpha**2 * (self.dim_x + self.kappa) - self.dim_x
        
        # Compute weights
        self._compute_weights()
        
        self.dt = 0.01
        self.initialized = False
        
        # Statistics
        self.NIS_history = []
        self.model_switches = 0
        self.current_model = 0
        
        log.info("22-State AUKF initialized")
    
    def _compute_weights(self):
        """Compute sigma point weights."""
        n = self.dim_x
        total = 2 * n + 1
        
        self.Wm = np.zeros(total)
        self.Wm[0] = self.lam / (n + self.lam)
        self.Wm[1:] = 1 / (2 * (n + self.lam))
        
        self.Wc = np.zeros(total)
        self.Wc[0] = self.lam / (n + self.lam) + (1 - self.alpha**2 + self.beta)
        self.Wc[1:] = 1 / (2 * (n + self.lam))
    
    def initialize(self, lat: float = 0, lon: float = 0, alt: float = 0,
                   vx: float = 0, vy: float = 0, vz: float = 0):
        """Initialize with starting position and velocity."""
        self.x[0] = lat
        self.x[1] = lon
        self.x[2] = alt
        self.x[3] = vx
        self.x[4] = vy
        self.x[5] = vz
        
        # Initialize quaternion (level hover)
        self.x[6] = 1.0  # qw
        self.x[7] = 0.0  # qx
        self.x[8] = 0.0  # qy
        self.x[9] = 0.0  # qz
        
        self.P = np.eye(self.dim_x) * 10
        self.initialized = True
        log.info("AUKF initialized with position")
    
    def _generate_sigma_points(self, Q: np.ndarray) -> np.ndarray:
        """Generate sigma points with current covariance + process noise."""
        n = self.dim_x
        
        P_aug = self.P + Q
        
        try:
            U = np.linalg.cholesky(P_aug)
        except np.linalg.LinAlgError:
            U = np.sqrt(P_aug + np.eye(n) * 1e-6) * np.sqrt(n)
        
        sigma_points = np.zeros((2 * n + 1, n))
        sigma_points[0] = self.x
        
        lambda_scale = np.sqrt(n + self.lam)
        
        for i in range(n):
            sigma_points[i + 1] = self.x + lambda_scale * U[i]
            sigma_points[n + 1 + i] = self.x - lambda_scale * U[i]
        
        return sigma_points
    
    def predict(self, accel: np.ndarray, gyro: np.ndarray, dt: float = 0.01) -> np.ndarray:
        """
        Prediction step with IMU data.
        
        Args:
            accel: Accelerometer reading [ax, ay, az]
            gyro: Gyroscope reading [gx, gy, gz]
            dt: Time step
        """
        if not self.initialized:
            self.initialize()
        
        self.dt = dt
        
        # Adapt process noise based on dynamics
        self._adapt_process_noise(accel, gyro)
        
        # Select best model
        Q = self._select_model()
        
        # Generate sigma points
        sigma_points = self._generate_sigma_points(Q)
        
        # Transform sigma points
        transformed = np.zeros_like(sigma_points)
        for i in range(len(sigma_points)):
            transformed[i] = self._state_transition(sigma_points[i], accel, gyro, dt)
        
        # Predicted state
        self.x = np.zeros(self.dim_x)
        for i in range(len(sigma_points)):
            self.x += self.Wm[i] * transformed[i]
        
        # Predicted covariance
        self.P = Q.copy()
        for i in range(len(sigma_points)):
            diff = transformed[i] - self.x
            self.P += self.Wc[i] * np.outer(diff, diff)
        
        return self.x.copy()
    
    def _state_transition(self, x: np.ndarray, accel: np.ndarray, 
                         gyro: np.ndarray, dt: float) -> np.ndarray:
        """State transition with IMU integration."""
        x_new = x.copy()
        
        # Quaternion integration
        q = x[6:10]
        omega = np.array([0, gyro[0], gyro[1], gyro[2]])
        q_dot = 0.5 * self._quaternion_multiply(q, omega)
        x_new[6:10] = q + q_dot * dt
        
        # Normalize quaternion
        x_new[6:10] = self._normalize_quaternion(x_new[6:10])
        
        # Position update from velocity
        x_new[0] += x[3] * dt
        x_new[1] += x[4] * dt
        x_new[2] += x[5] * dt
        
        # Add accelerometer effect (subtract gravity)
        gravity = np.array([0, 0, -9.81])
        accel_corrected = accel - gravity
        
        # Update velocity
        x_new[3] += (accel_corrected[0] - x[10]) * dt  # Subtract accel bias
        x_new[4] += (accel_corrected[1] - x[11]) * dt
        x_new[5] += (accel_corrected[2] - x[12]) * dt
        
        # Wind effect on velocity
        x_new[3] += x[16] * dt
        x_new[4] += x[17] * dt
        x_new[5] += x[18] * dt
        
        return x_new
    
    def _quaternion_multiply(self, q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Multiply two quaternions."""
        result = np.zeros(4)
        result[0] = q1[0]*q2[0] - q1[1]*q2[1] - q1[2]*q2[2] - q1[3]*q2[3]
        result[1] = q1[0]*q2[1] + q1[1]*q2[0] + q1[2]*q2[3] - q1[3]*q2[2]
        result[2] = q1[0]*q2[2] - q1[1]*q2[3] + q1[2]*q2[0] + q1[3]*q2[1]
        result[3] = q1[0]*q2[3] + q1[1]*q2[2] - q1[2]*q2[1] + q1[3]*q2[0]
        return result
    
    def _normalize_quaternion(self, q: np.ndarray) -> np.ndarray:
        """Normalize quaternion."""
        norm = np.linalg.norm(q)
        if norm > 0:
            return q / norm
        return np.array([1, 0, 0, 0])
    
    def update(self, gps: Dict, baro_alt: float = None) -> Tuple[np.ndarray, float]:
        """
        Update step with GPS and barometer measurements.
        
        Args:
            gps: GPS measurement {'lat', 'lon', 'alt', 'vx', 'vy', 'vz'}
            baro_alt: Barometer altitude (optional)
            
        Returns:
            (updated_state, NIS)
        """
        if not self.initialized:
            self.initialize()
        
        # Build measurement vector
        z = np.zeros(self.dim_z)
        z[0] = gps['lat']
        z[1] = gps['lon']
        z[2] = gps['alt']
        z[3] = gps.get('vx', 0)
        z[4] = gps.get('vy', 0)
        z[5] = gps.get('vz', 0)
        
        # Measurement prediction
        z_pred = self.x[:self.dim_z]
        
        # Innovation
        y = z - z_pred
        
        # Store innovation for adaptation
        self.innovation_history.append(np.linalg.norm(y))
        if len(self.innovation_history) > self.max_history:
            self.innovation_history.pop(0)
        
        # Adapt measurement noise
        self._adapt_measurement_noise(y)
        
        # Compute measurement Jacobian
        H = self._compute_jacobian()
        
        # Innovation covariance
        S = H @ self.P @ H.T + self.R
        
        # Kalman gain
        K = self.P @ H.T @ np.linalg.inv(S)
        
        # Update state
        self.x = self.x + K @ y
        
        # Update covariance
        self.P = (np.eye(self.dim_x) - K @ H) @ self.P
        
        # NIS for consistency check
        NIS = float(y.T @ np.linalg.inv(S) @ y)
        
        # Update model probabilities
        self._update_model_probabilities(NIS)
        
        self.NIS_history.append(NIS)
        if len(self.NIS_history) > 100:
            self.NIS_history.pop(0)
        
        return self.x.copy(), NIS
    
    def _compute_jacobian(self) -> np.ndarray:
        """Compute measurement Jacobian."""
        H = np.zeros((self.dim_z, self.dim_x))
        
        # Direct measurement of position and velocity
        for i in range(self.dim_z):
            H[i, i] = 1.0
        
        return H
    
    def _adapt_process_noise(self, accel: np.ndarray, gyro: np.ndarray):
        """Adapt process noise based on dynamics."""
        accel_mag = np.linalg.norm(accel)
        gyro_mag = np.linalg.norm(gyro)
        
        # High dynamics = more process noise
        if accel_mag > 15 or gyro_mag > 3:
            self.Q = self.model_Q[2]  # High maneuver model
        elif accel_mag > 5 or gyro_mag > 0.5:
            self.Q = self.model_Q[1]  # Degraded model
        else:
            self.Q = self.model_Q[0]  # Normal model
    
    def _adapt_measurement_noise(self, innovation: np.ndarray):
        """Adapt measurement noise based on innovation."""
        innovation_mag = np.linalg.norm(innovation)
        
        # If innovation is large, increase measurement noise
        if innovation_mag > 10:
            self.R = np.eye(self.dim_z) * 10
        elif innovation_mag > 5:
            self.R = np.eye(self.dim_z) * 2
        else:
            self.R = np.eye(self.dim_z) * 1
    
    def _select_model(self) -> np.ndarray:
        """Select best process noise model."""
        # Use weighted combination
        Q = np.zeros((self.dim_x, self.dim_x))
        for i, w in enumerate(self.model_weights):
            Q += w * self.model_Q[i]
        return Q
    
    def _update_model_probabilities(self, NIS: float):
        """Update model probabilities based on NIS."""
        # Likelihood based on NIS
        expected_NIS = self.dim_z
        likelihood = np.exp(-0.5 * (NIS - expected_NIS)**2 / expected_NIS)
        
        # Update weights
        for i in range(len(self.model_weights)):
            if i == self.current_model:
                self.model_weights[i] = 0.9 * self.model_weights[i] + 0.1 * likelihood
            else:
                self.model_weights[i] = 0.9 * self.model_weights[i]
        
        # Normalize
        self.model_weights /= np.sum(self.model_weights)
        
        # Switch model if confidence is high
        best_model = np.argmax(self.model_weights)
        if self.model_weights[best_model] > 0.7 and best_model != self.current_model:
            self.current_model = best_model
            self.model_switches += 1
            log.info(f"AUKF: Switched to model {best_model}")
    
    def update_no_gps(self, baro_alt: float, imu_data: Dict):
        """
        Update without GPS (dead reckoning).
        
        Args:
            baro_alt: Barometer altitude
            imu_data: IMU readings
        """
        if not self.initialized:
            return
        
        # Use barometer for altitude
        alt_innovation = baro_alt - self.x[2] - self.x[19]  # Subtract baro bias
        
        # Simple altitude update
        K_alt = 0.3
        self.x[2] += K_alt * alt_innovation
        
        # Increase uncertainty
        self.P[2, 2] += 0.1
        self.P[3, 3] += 0.01
        self.P[4, 4] += 0.01
    
    def get_position_llh(self) -> Tuple[float, float, float]:
        """Get position as lat, lon, altitude."""
        return self.x[0], self.x[1], self.x[2]
    
    def get_velocity_ned(self) -> Tuple[float, float, float]:
        """Get velocity as N, E, D."""
        return self.x[3], self.x[4], self.x[5]
    
    def get_attitude_euler(self) -> Tuple[float, float, float]:
        """Get attitude as roll, pitch, yaw (degrees)."""
        q = self.x[6:10]
        
        # Quaternion to Euler
        roll = np.arctan2(2*(q[0]*q[1] + q[2]*q[3]), 1 - 2*(q[1]**2 + q[2]**2))
        pitch = np.arcsin(2*(q[0]*q[2] - q[3]*q[1]))
        yaw = np.arctan2(2*(q[0]*q[3] + q[1]*q[2]), 1 - 2*(q[2]**2 + q[3]**2))
        
        return np.degrees(roll), np.degrees(pitch), np.degrees(yaw)
    
    def get_biases(self) -> Dict:
        """Get estimated sensor biases."""
        return {
            'gyro_bias': self.x[10:13].tolist(),
            'accel_bias': self.x[13:16].tolist(),
            'baro_bias': self.x[19],
            'wind': self.x[16:19].tolist()
        }
    
    def get_state(self) -> Dict:
        """Get full state as dictionary."""
        roll, pitch, yaw = self.get_attitude_euler()
        
        return {
            'position': {
                'lat': self.x[0],
                'lon': self.x[1],
                'alt': self.x[2]
            },
            'velocity': {
                'vn': self.x[3],
                've': self.x[4],
                'vd': self.x[5]
            },
            'attitude': {
                'roll': roll,
                'pitch': pitch,
                'yaw': yaw
            },
            'quaternion': self.x[6:10].tolist(),
            'biases': self.get_biases(),
            'model': self.current_model,
            'model_weights': self.model_weights.tolist(),
            'model_switches': self.model_switches,
            'NIS': self.NIS_history[-1] if self.NIS_history else 0,
            'covariance': self.P
        }
    
    def reset(self):
        """Reset filter."""
        self.x = np.zeros(self.dim_x)
        self.P = np.eye(self.dim_x) * 10
        self.model_weights = np.ones(3) / 3
        self.current_model = 0
        self.innovation_history.clear()
        self.NIS_history.clear()
        self.initialized = False