"""
SkyCore Geometric Controller
============================
Geometric tracking controller for quadrotors.
"""

import numpy as np
from typing import Tuple, Dict
import logging

log = logging.getLogger(__name__)


class GeometricController:
    """
    Geometric Controller for quadrotor attitude control.
    
    Uses SE(3) geometric control for aggressive maneuvering.
    Provides smooth tracking with attitude constraints.
    """
    
    def __init__(self, mass: float = 1.0, gravity: float = 9.81,
                 inertia: Tuple[float, float, float] = (0.01, 0.01, 0.02)):
        """
        Initialize geometric controller.
        
        Args:
            mass: Quadrotor mass (kg)
            gravity: Gravity (m/s^2)
            inertia: Moment of inertia (Ix, Iy, Iz)
        """
        self.m = mass
        self.g = gravity
        self.I = np.diag(inertia)
        
        # Gains
        self.kx = np.diag([5.0, 5.0, 5.0])      # Position
        self.kv = np.diag([4.0, 4.0, 4.0])       # Velocity
        self.kR = np.diag([5.0, 5.0, 5.0])        # Attitude
        self.kw = np.diag([1.0, 1.0, 1.5])       # Angular velocity
        
        # Max values
        self.max_tilt = np.radians(45)
        self.max_thrust = 25.0  # m/s^2
        self.max_rate = np.radians(180)
        
    def compute_control(self, pos: np.ndarray, vel: np.ndarray,
                      att: np.ndarray, omega: np.ndarray,
                      pos_des: np.ndarray, vel_des: np.ndarray,
                      acc_des: np.ndarray, yaw_des: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute control inputs.
        
        Args:
            pos, vel: Current position and velocity (NED)
            att: Current attitude quaternion [qw, qx, qy, qz]
            omega: Angular velocity [wx, wy, wz]
            pos_des, vel_des, acc_des: Desired trajectory
            yaw_des: Desired yaw angle
            
        Returns:
            (thrust, moment) - thrust scalar and moment vector
        """
        # Rotation matrices
        R = self._quaternion_to_rotation(att)
        R_des = self._euler_to_rotation(0, 0, yaw_des)
        
        # Position error
        ex = pos_des - pos
        ev = vel_des - vel
        
        # Desired acceleration in inertial frame
        a_des = acc_des + self.kx @ ex + self.kv @ ev
        
        # Desired thrust direction
        b3_des = a_des / np.linalg.norm(a_des)
        b3 = R[:, 2]
        
        # Thrust magnitude
        f = self.m * np.dot(a_des, b3)
        f = np.clip(f, 0, self.m * self.max_thrust)
        
        # Cross product for attitude correction
        b3_cross = np.cross(b3, b3_des)
        
        # Desired rotation matrix
        x_c_des = np.array([np.cos(yaw_des), np.sin(yaw_des), 0])
        y_c_des = np.cross(b3_des, x_c_des)
        R_des_col = np.column_stack([np.cross(y_c_des, b3_des), y_c_des, b3_des])
        
        # Error rotation matrix
        Re = 0.5 * (R_des_col.T @ R - R.T @ R_des_col)
        skew_Re = self._vee(Re)
        
        # Attitude error
        eR = skew_Re
        ew = omega  # Angular velocity error (assuming desired = 0)
        
        # Moment command
        M = -self.kR @ eR - self.kw @ ew + np.cross(omega, self.I @ omega)
        
        # Limit moments
        M = np.clip(M, -1.0, 1.0)
        
        return np.array([f]), M
    
    def _quaternion_to_rotation(self, q: np.ndarray) -> np.ndarray:
        """Convert quaternion to rotation matrix."""
        q0, q1, q2, q3 = q
        
        R = np.zeros((3, 3))
        R[0, 0] = 1 - 2*(q2**2 + q3**2)
        R[0, 1] = 2*(q1*q2 - q0*q3)
        R[0, 2] = 2*(q1*q3 + q0*q2)
        R[1, 0] = 2*(q1*q2 + q0*q3)
        R[1, 1] = 1 - 2*(q1**2 + q3**2)
        R[1, 2] = 2*(q2*q3 - q0*q1)
        R[2, 0] = 2*(q1*q3 - q0*q2)
        R[2, 1] = 2*(q2*q3 + q0*q1)
        R[2, 2] = 1 - 2*(q1**2 + q2**2)
        
        return R
    
    def _euler_to_rotation(self, roll: float, pitch: float, yaw: float) -> np.ndarray:
        """Convert Euler angles to rotation matrix."""
        cr, cp, cy = np.cos([roll, pitch, yaw])
        sr, sp, sy = np.sin([roll, pitch, yaw])
        
        R = np.array([
            [cr*cp, sr*cy + cr*sp*sy, sr*sy - cr*sp*cy],
            [-sr*cp, cr*cy - sr*sp*sy, cr*sy + sr*sp*cy],
            [sp, -cp*sy, cp*cy]
        ])
        
        return R
    
    def _vee(self, skew: np.ndarray) -> np.ndarray:
        """Extract vector from skew-symmetric matrix."""
        return np.array([skew[2, 1], skew[0, 2], skew[1, 0]])
    
    def set_gains(self, kx: np.ndarray, kv: np.ndarray, kR: np.ndarray, kw: np.ndarray):
        """Set controller gains."""
        self.kx = kx
        self.kv = kv
        self.kR = kR
        self.kw = kw
    
    def get_state(self) -> Dict:
        """Get controller state."""
        return {
            'mass': self.m,
            'gravity': self.g,
            'inertia': self.I.diagonal().tolist(),
            'gains': {
                'kx': self.kx.diagonal().tolist(),
                'kv': self.kv.diagonal().tolist(),
                'kR': self.kR.diagonal().tolist(),
                'kw': self.kw.diagonal().tolist()
            }
        }