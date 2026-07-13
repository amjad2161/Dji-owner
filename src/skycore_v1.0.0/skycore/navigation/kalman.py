"""
SkyCore Kalman Filter
====================
Basic linear Kalman filter for state estimation.
"""

import numpy as np
from typing import Dict, Optional, Tuple
import logging

log = logging.getLogger(__name__)


class KalmanFilter:
    """
    Linear Kalman Filter for state estimation.
    
    Implements:
    - Prediction step
    - Update step
    - State extraction
    """
    
    def __init__(self, dim_x: int = 16, dim_z: int = 6):
        """
        Initialize Kalman Filter.
        
        Args:
            dim_x: State dimension
            dim_z: Measurement dimension
        """
        self.dim_x = dim_x
        self.dim_z = dim_z
        
        # State estimate
        self.x = np.zeros(dim_x)
        
        # Error covariance
        self.P = np.eye(dim_x) * 100
        
        # State transition matrix
        self.F = np.eye(dim_x)
        
        # Measurement matrix
        self.H = np.zeros((dim_z, dim_x))
        
        # Measurement noise
        self.R = np.eye(dim_z) * 1.0
        
        # Process noise
        self.Q = np.eye(dim_x) * 0.1
        
        # Time step
        self.dt = 0.01
        
        self.initialized = False
    
    def initialize(self, initial_state: np.ndarray, initial_covariance: Optional[np.ndarray] = None):
        """Initialize filter with initial state and covariance."""
        self.x = initial_state.copy()
        if initial_covariance is not None:
            self.P = initial_covariance.copy()
        else:
            self.P = np.eye(self.dim_x) * 10
        self.initialized = True
        log.info("Kalman Filter initialized")
    
    def predict(self, dt: Optional[float] = None) -> np.ndarray:
        """
        Prediction step.
        
        Args:
            dt: Time step (seconds)
            
        Returns:
            Predicted state
        """
        if not self.initialized:
            return self.x
        
        if dt is not None:
            self.dt = dt
            self._update_transition_matrix()
        
        # Predict state
        self.x = self.F @ self.x
        
        # Predict covariance
        self.P = self.F @ self.P @ self.F.T + self.Q
        
        return self.x.copy()
    
    def update(self, z: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Update step with measurement.
        
        Args:
            z: Measurement vector
            
        Returns:
            (updated_state, innovation_squared)
        """
        if not self.initialized:
            self.initialize(np.zeros(self.dim_x))
        
        # Innovation (measurement residual)
        y = z - self.H @ self.x
        
        # Innovation covariance
        S = self.H @ self.P @ self.H.T + self.R
        
        # Kalman gain
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # Update state
        self.x = self.x + K @ y
        
        # Update covariance
        I_KH = np.eye(self.dim_x) - K @ self.H
        self.P = I_KH @ self.P
        
        # Normalized innovation squared (for consistency check)
        NIS = y.T @ np.linalg.inv(S) @ y
        
        return self.x.copy(), NIS
    
    def _update_transition_matrix(self):
        """Update state transition matrix based on dt."""
        # For constant velocity model
        # State: [x, y, z, vx, vy, vz, ...]
        self.F = np.eye(self.dim_x)
        
        # Position updates from velocity
        for i in range(3):
            self.F[i, i+3] = self.dt
    
    def get_state(self, indices: list) -> np.ndarray:
        """Get specific elements of state vector."""
        return self.x[indices]
    
    def get_position(self) -> Tuple[float, float, float]:
        """Get position estimate (x, y, z)."""
        return self.x[0], self.x[1], self.x[2]
    
    def get_velocity(self) -> Tuple[float, float, float]:
        """Get velocity estimate (vx, vy, vz)."""
        return self.x[3], self.x[4], self.x[5]
    
    def get_full_state(self) -> Dict:
        """Get full state as dictionary."""
        return {
            'position': self.get_position(),
            'velocity': self.get_velocity(),
            'attitude': self.x[6:9].tolist() if len(self.x) >= 9 else [0, 0, 0],
            'covariance': self.P
        }
    
    def reset(self):
        """Reset filter to initial state."""
        self.x = np.zeros(self.dim_x)
        self.P = np.eye(self.dim_x) * 100
        self.initialized = False


def create_kalman_filter(state_type: str = "position") -> KalmanFilter:
    """Factory function to create configured Kalman filters."""
    
    if state_type == "position":
        # 6DOF: position and velocity
        return KalmanFilter(dim_x=6, dim_z=3)
    elif state_type == "full":
        # 16DOF: full state with quaternion
        kf = KalmanFilter(dim_x=16, dim_z=6)
        kf.Q = np.eye(16) * 0.05
        return kf
    else:
        return KalmanFilter()