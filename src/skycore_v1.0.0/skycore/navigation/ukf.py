"""
SkyCore Unscented Kalman Filter (UKF)
====================================
Sigma-point Kalman filter for highly non-linear systems.
"""

import numpy as np
from typing import Dict, Tuple, Optional, List, Union, Any
import logging

log = logging.getLogger(__name__)


class UnscentedKalmanFilter:
    """
    Unscented Kalman Filter using sigma points.
    
    Better for non-linear systems than EKF.
    Uses sigma point transformation.
    """
    
    def __init__(self, dim_x: int = 16, dim_z: int = 6, alpha: float = 0.001, beta: float = 2.0, kappa: float = 0.0):
        """
        Initialize UKF.
        
        Args:
            dim_x: State dimension
            dim_z: Measurement dimension
            alpha: Spread parameter (0.001 to 1)
            beta: Prior knowledge parameter (2 for Gaussian)
            kappa: Secondary scaling parameter
        """
        self.dim_x = dim_x
        self.dim_z = dim_z
        self.alpha = alpha
        self.beta = beta
        self.kappa = kappa
        
        # State estimate
        self.x = np.zeros(dim_x)
        
        # Error covariance
        self.P = np.eye(dim_x)
        
        # Process noise
        self.Q = np.eye(dim_x) * 0.01
        
        # Measurement noise
        self.R = np.eye(dim_z)
        
        # Lambda parameter
        self.lam = alpha**2 * (dim_x + kappa) - dim_x
        
        # Sigma point weights
        self._compute_weights()
        
        self.dt = 0.01
        self.initialized = False
    
    def _compute_weights(self):
        """Compute sigma point weights."""
        n = self.dim_x
        total = 2 * n + 1
        
        # Mean weights
        self.Wm = np.zeros(total)
        self.Wm[0] = self.lam / (n + self.lam)
        self.Wm[1:] = 1 / (2 * (n + self.lam))
        
        # Covariance weights
        self.Wc = np.zeros(total)
        self.Wc[0] = self.lam / (n + self.lam) + (1 - self.alpha**2 + self.beta)
        self.Wc[1:] = 1 / (2 * (n + self.lam))
    
    def initialize(self, initial_state: np.ndarray):
        """Initialize UKF."""
        self.x = initial_state.copy()
        self.P = np.eye(self.dim_x) * 10
        self.initialized = True
        log.info("UKF initialized")
    
    def _generate_sigma_points(self) -> np.ndarray:
        """Generate sigma points."""
        n = self.dim_x
        
        # Square root of covariance
        try:
            U = np.linalg.cholesky(self.P)
        except np.linalg.LinAlgError:
            U = np.sqrt(self.P + np.eye(n) * 1e-6) * np.sqrt(n)
        
        sigma_points = np.zeros((2 * n + 1, n))
        
        # Mean point
        sigma_points[0] = self.x
        
        # Symmetric points
        for i in range(n):
            lambda_scale = np.sqrt(n + self.lam)
            sigma_points[i + 1] = self.x + lambda_scale * U[i]
            sigma_points[n + 1 + i] = self.x - lambda_scale * U[i]
        
        return sigma_points
    
    def predict(self, dt: Optional[float] = None) -> np.ndarray:
        """
        UKF prediction step.
        """
        if not self.initialized:
            return self.x
        
        if dt is not None:
            self.dt = dt
        
        # Generate sigma points
        sigma_points = self._generate_sigma_points()
        
        # Transform sigma points through state transition
        transformed = np.zeros_like(sigma_points)
        for i in range(len(sigma_points)):
            transformed[i] = self._state_transition(sigma_points[i], self.dt)
        
        # Compute predicted state
        self.x = np.zeros(self.dim_x)
        for i in range(len(sigma_points)):
            self.x += self.Wm[i] * transformed[i]
        
        # Compute predicted covariance
        self.P = self.Q.copy()
        for i in range(len(sigma_points)):
            diff = transformed[i] - self.x
            self.P += self.Wc[i] * np.outer(diff, diff)
        
        return self.x.copy()
    
    def update(self, z: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        UKF update step.
        """
        if not self.initialized:
            self.initialize(np.zeros(self.dim_x))
        
        # Generate sigma points
        sigma_points = self._generate_sigma_points()
        
        # Transform through measurement function
        z_pred_points = np.zeros((len(sigma_points), self.dim_z))
        for i in range(len(sigma_points)):
            z_pred_points[i] = self._measurement_function(sigma_points[i])
        
        # Predicted measurement
        z_pred = np.zeros(self.dim_z)
        for i in range(len(sigma_points)):
            z_pred += self.Wm[i] * z_pred_points[i]
        
        # Innovation
        y = z - z_pred
        
        # Innovation covariance
        S = self.R.copy()
        for i in range(len(sigma_points)):
            diff = z_pred_points[i] - z_pred
            S += self.Wc[i] * np.outer(diff, diff)
        
        # Cross covariance
        Pxz = np.zeros((self.dim_x, self.dim_z))
        for i in range(len(sigma_points)):
            x_diff = sigma_points[i] - self.x
            z_diff = z_pred_points[i] - z_pred
            Pxz += self.Wc[i] * np.outer(x_diff, z_diff)
        
        # Kalman gain
        K = Pxz @ np.linalg.inv(S)
        
        # Update state
        self.x = self.x + K @ y
        
        # Update covariance
        self.P = self.P - K @ S @ K.T
        
        # NIS
        NIS = float(y.T @ np.linalg.inv(S) @ y)
        
        return self.x.copy(), NIS
    
    def _state_transition(self, x: np.ndarray, dt: float) -> np.ndarray:
        """State transition function."""
        x_new = x.copy()
        if len(x) >= 6:
            x_new[0] = x[0] + x[3] * dt
            x_new[1] = x[1] + x[4] * dt
            x_new[2] = x[2] + x[5] * dt
        return x_new
    
    def _measurement_function(self, x: np.ndarray) -> np.ndarray:
        """Measurement function."""
        # Direct measurement of position and velocity
        return x[:self.dim_z]
    
    def get_position(self) -> Tuple[float, float, float]:
        """Get estimated position."""
        return self.x[0], self.x[1], self.x[2]
    
    def get_velocity(self) -> Tuple[float, float, float]:
        """Get estimated velocity."""
        return self.x[3], self.x[4], self.x[5]
    
    def get_state(self) -> Dict:
        """Get full state."""
        return {
            'position': self.get_position(),
            'velocity': self.get_velocity(),
            'raw_state': self.x,
            'covariance': self.P
        }
    
    def reset(self):
        """Reset filter."""
        self.x = np.zeros(self.dim_x)
        self.P = np.eye(self.dim_x)
        self.initialized = False