"""
SkyCore LQR Controller
======================
Linear Quadratic Regulator for drone control.
"""

import numpy as np
from typing import Tuple, Optional
import logging

log = logging.getLogger(__name__)


class LQRController:
    """
    LQR Controller for drone attitude and position control.
    
    Uses state feedback to minimize quadratic cost function.
    """
    
    def __init__(self, A: np.ndarray, B: np.ndarray,
                 Q: np.ndarray, R: np.ndarray):
        """
        Initialize LQR controller.
        
        Args:
            A: State transition matrix
            B: Control input matrix
            Q: State cost matrix
            R: Control cost matrix
        """
        self.A = A
        self.B = B
        self.Q = Q
        self.R = R
        
        # Compute LQR gain matrix
        self.K, self.S, self.eigenvalues = self._compute_lqr_gain()
        
        self.n_states = A.shape[0]
        self.n_controls = B.shape[1]
    
    def _compute_lqr_gain(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Solve Riccati equation for LQR gain."""
        from scipy.linalg import solve
        
        # Discrete-time algebraic Riccati equation
        # P = Q + A^T P A - A^T P B (R + B^T P B)^-1 B^T P A
        
        P = self.Q.copy()
        max_iter = 100
        tolerance = 1e-8
        
        for _ in range(max_iter):
            # Compute P_new
            P_new = self.Q + self.A.T @ P @ self.A - \
                   self.A.T @ P @ self.B @ \
                   np.linalg.inv(self.R + self.B.T @ P @ self.B) @ \
                   self.B.T @ P @ self.A
            
            # Check convergence
            if np.max(np.abs(P_new - P)) < tolerance:
                P = P_new
                break
            
            P = P_new
        
        # LQR gain
        K = np.linalg.inv(self.R + self.B.T @ P @ self.B) @ self.B.T @ P @ self.A
        
        # Eigenvalues of closed-loop system
        eigenvalues = np.linalg.eigvals(self.A - self.B @ K)
        
        return K, P, eigenvalues
    
    def compute(self, x: np.ndarray, x_des: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Compute control input.
        
        Args:
            x: Current state vector
            x_des: Desired state (if None, assume origin)
            
        Returns:
            Control input vector
        """
        if x_des is None:
            error = x
        else:
            error = x - x_des
        
        # LQR control law
        u = -self.K @ error
        
        return u
    
    def update_matrices(self, A: np.ndarray, B: np.ndarray):
        """Update system matrices and recompute gain."""
        self.A = A
        self.B = B
        self.K, self.S, self.eigenvalues = self._compute_lqr_gain()
    
    def get_gain_matrix(self) -> np.ndarray:
        """Get LQR gain matrix."""
        return self.K
    
    def get_closed_loop_poles(self) -> np.ndarray:
        """Get closed-loop eigenvalues."""
        return self.eigenvalues


class CascadedLQRController:
    """
    Cascaded LQR controller for multi-level control.
    
    Outer loop: Position
    Inner loop: Velocity
    Innermost loop: Attitude
    """
    
    def __init__(self, mass: float = 1.0, gravity: float = 9.81):
        """
        Initialize cascaded LQR.
        
        Args:
            mass: Quadrotor mass
            gravity: Gravity
        """
        self.m = mass
        self.g = gravity
        
        # Time constants for tuning
        self.T_position = 1.0
        self.T_velocity = 0.5
        self.T_attitude = 0.1
        
        # Initialize LQR controllers
        self._init_position_controller()
        self._init_velocity_controller()
        self._init_attitude_controller()
    
    def _init_position_controller(self):
        """Initialize position LQR."""
        # 3D position + 3D velocity = 6 states, 3 thrust
        A = np.zeros((6, 6))
        A[:3, 3:] = np.eye(3)
        
        B = np.zeros((6, 3))
        B[3:, :] = np.eye(3) / self.m
        
        Q = np.diag([10, 10, 10, 1, 1, 1])  # Position more important
        R = np.diag([1, 1, 1])
        
        try:
            self.pos_lqr = LQRController(A, B, Q, R)
        except:
            self.pos_lqr = None
    
    def _init_velocity_controller(self):
        """Initialize velocity LQR."""
        # 3D velocity, 3D angular rate = 6 states, 3 forces
        A = np.zeros((6, 6))
        A[:3, 3:] = np.eye(3)
        
        B = np.zeros((6, 3))
        B[3:, :] = np.eye(3)
        
        Q = np.diag([1, 1, 1, 1, 1, 1])
        R = np.diag([0.5, 0.5, 0.5])
        
        try:
            self.vel_lqr = LQRController(A, B, Q, R)
        except:
            self.vel_lqr = None
    
    def _init_attitude_controller(self):
        """Initialize attitude LQR."""
        # Attitude (quaternion) + angular rate
        A = np.zeros((6, 6))
        A[:3, 3:] = np.eye(3)
        
        B = np.zeros((6, 3))
        B[3:, :] = np.eye(3)
        
        Q = np.diag([5, 5, 5, 1, 1, 1])
        R = np.diag([0.1, 0.1, 0.1])
        
        try:
            self.att_lqr = LQRController(A, B, Q, R)
        except:
            self.att_lqr = None
    
    def compute(self, pos: np.ndarray, vel: np.ndarray,
               att: np.ndarray, omega: np.ndarray,
               pos_des: np.ndarray, vel_des: np.ndarray,
               acc_des: np.ndarray, yaw_des: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute cascaded LQR control.
        
        Returns:
            (thrust, moment)
        """
        # Position loop (outer)
        pos_state = np.concatenate([pos - pos_des, vel - vel_des])
        if self.pos_lqr:
            force_des = self.pos_lqr.compute(pos_state)
        else:
            force_des = np.zeros(3)
        
        # Add gravity
        f_total = force_des + np.array([0, 0, self.m * self.g])
        
        # Thrust magnitude
        thrust = np.linalg.norm(f_total)
        
        # Desired thrust direction
        thrust_dir = f_total / thrust if thrust > 0 else np.array([0, 0, 1])
        
        # Attitude from thrust direction
        # (simplified - use yaw to align)
        R_des = self._thrust_to_rotation(thrust_dir, yaw_des)
        
        # Attitude error
        att_error = self._attitude_error(att, R_des)
        
        # Attitude loop (inner)
        att_state = np.concatenate([att_error, omega])
        if self.att_lqr:
            moment = self.att_lqr.compute(att_state)
        else:
            moment = np.zeros(3)
        
        return np.array([thrust]), moment
    
    def _thrust_to_rotation(self, thrust_dir: np.ndarray, yaw: float) -> np.ndarray:
        """Compute desired rotation from thrust direction."""
        z_body = thrust_dir
        x_world = np.array([np.cos(yaw), np.sin(yaw), 0])
        y_body = np.cross(z_body, x_world)
        y_body /= np.linalg.norm(y_body)
        x_body = np.cross(y_body, z_body)
        
        return np.column_stack([x_body, y_body, z_body])
    
    def _attitude_error(self, q: np.ndarray, R_des: np.ndarray) -> np.ndarray:
        """Compute attitude error."""
        R = self._quaternion_to_rotation(q)
        
        # Error rotation matrix
        R_err = R_des.T @ R
        
        # Axis-angle representation
        trace = np.trace(R_err)
        angle = np.arccos(np.clip((trace - 1) / 2, -1, 1))
        
        if angle < 1e-6:
            return np.zeros(3)
        
        axis = np.array([
            R_err[2, 1] - R_err[1, 2],
            R_err[0, 2] - R_err[2, 0],
            R_err[1, 0] - R_err[0, 1]
        ]) / (2 * np.sin(angle))
        
        return axis * angle
    
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