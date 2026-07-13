"""
SkyCore Extended Kalman Filter (EKF)
====================================
Non-linear Kalman filter using Jacobian linearization.
"""

import numpy as np
from typing import Dict, Optional, Tuple
import logging

log = logging.getLogger(__name__)


class ExtendedKalmanFilter:
    """
    Extended Kalman Filter for non-linear systems.
    
    Uses Jacobian matrices for linearization.
    Suitable for attitude estimation and navigation.
    """
    
    def __init__(self, dim_x: int = 16, dim_z: int = 6):
        """
        Initialize EKF.
        
        Args:
            dim_x: State dimension
            dim_z: Measurement dimension
        """
        self.dim_x = dim_x
        self.dim_z = dim_z
        
        # State estimate
        self.x = np.zeros(dim_x)
        
        # Error covariance
        self.P = np.eye(dim_x)
        
        # Process noise covariance
        self.Q = np.eye(dim_x) * 0.01
        
        # Measurement noise covariance
        self.R = np.eye(dim_z)
        
        # Time step
        self.dt = 0.01
        
        self.initialized = False
    
    def initialize(self, initial_state: np.ndarray):
        """Initialize with starting state."""
        self.x = initial_state.copy()
        self.P = np.eye(self.dim_x) * 10
        self.initialized = True
        log.info("EKF initialized")
    
    def predict(self, dt: Optional[float] = None) -> np.ndarray:
        """
        Prediction step with non-linear state transition.
        
        Args:
            dt: Time step
            
        Returns:
            Predicted state
        """
        if not self.initialized:
            return self.x
        
        if dt is not None:
            self.dt = dt
        
        # Non-linear state transition
        self.x = self._state_transition(self.x, self.dt)
        
        # Linearize and compute Jacobian
        F = self._compute_jacobian_f(self.x, self.dt)
        
        # Predict covariance
        self.P = F @ self.P @ F.T + self.Q
        
        return self.x.copy()
    
    def update(self, z: np.ndarray, measurement_function: Optional[callable] = None) -> Tuple[np.ndarray, float]:
        """
        Update step with measurement.
        
        Args:
            z: Measurement
            measurement_function: Optional custom measurement function
            
        Returns:
            (updated_state, NIS)
        """
        if not self.initialized:
            self.initialize(np.zeros(self.dim_x))
        
        # Use provided measurement function or default
        if measurement_function is None:
            z_pred = self.x[:self.dim_z]  # Direct measurement
        else:
            z_pred = measurement_function(self.x)
        
        # Innovation
        y = z - z_pred
        
        # Linearize measurement matrix
        H = self._compute_jacobian_h(z_pred)
        
        # Innovation covariance
        S = H @ self.P @ H.T + self.R
        
        # Kalman gain
        K = self.P @ H.T @ np.linalg.inv(S)
        
        # Update state
        self.x = self.x + K @ y
        
        # Update covariance
        I_KH = np.eye(self.dim_x) - K @ H
        self.P = I_KH @ self.P
        
        # Normalized innovation squared
        NIS = float(y.T @ np.linalg.inv(S) @ y)
        
        return self.x.copy(), NIS
    
    def _state_transition(self, x: np.ndarray, dt: float) -> np.ndarray:
        """
        Non-linear state transition function.
        
        State: [pos, vel, quat, bias, ...]
        """
        x_new = x.copy()
        
        # Position update from velocity
        if len(x) >= 6:
            x_new[0] = x[0] + x[3] * dt  # x
            x_new[1] = x[1] + x[4] * dt  # y
            x_new[2] = x[2] + x[5] * dt  # z
        
        return x_new
    
    def _compute_jacobian_f(self, x: np.ndarray, dt: float) -> np.ndarray:
        """
        Compute Jacobian of state transition.
        """
        F = np.eye(self.dim_x)
        
        # Position from velocity
        F[0, 3] = dt  # x from vx
        F[1, 4] = dt  # y from vy
        F[2, 5] = dt  # z from vz
        
        return F
    
    def _compute_jacobian_h(self, z_pred: np.ndarray) -> np.ndarray:
        """
        Compute Jacobian of measurement function.
        """
        H = np.zeros((self.dim_z, self.dim_x))
        
        # Direct measurement of first dim_z states
        for i in range(min(self.dim_z, self.dim_x)):
            H[i, i] = 1.0
        
        return H
    
    def set_process_noise(self, q: float):
        """Set process noise magnitude."""
        self.Q = np.eye(self.dim_x) * q
    
    def set_measurement_noise(self, r: float):
        """Set measurement noise magnitude."""
        self.R = np.eye(self.dim_z) * r
    
    def get_position(self) -> Tuple[float, float, float]:
        """Get estimated position."""
        return self.x[0], self.x[1], self.x[2]
    
    def get_velocity(self) -> Tuple[float, float, float]:
        """Get estimated velocity."""
        return self.x[3], self.x[4], self.x[5]
    
    def get_state(self) -> Dict:
        """Get full state as dictionary."""
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