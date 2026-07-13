"""
SkyCore MPC Controller
======================
Model Predictive Controller for drone trajectory tracking.
"""

import numpy as np
from typing import Tuple, List, Optional
from scipy.linalg import solve
import logging

log = logging.getLogger(__name__)


class MPCController:
    """
    Model Predictive Controller for drone control.
    
    Solves constrained optimization problem at each time step.
    """
    
    def __init__(self, A: np.ndarray, B: np.ndarray,
                 Q: np.ndarray, R: np.ndarray,
                 horizon: int = 10, dt: float = 0.1):
        """
        Initialize MPC controller.
        
        Args:
            A, B: State-space matrices
            Q, R: Cost matrices
            horizon: Prediction horizon (steps)
            dt: Time step
        """
        self.A = A
        self.B = B
        self.Q = Q
        self.R = R
        self.N = horizon
        self.dt = dt
        
        self.n_states = A.shape[0]
        self.n_controls = B.shape[1]
        
        # Build cost matrices
        self._build_mpc_matrices()
    
    def _build_mpc_matrices(self):
        """Build MPC cost and constraint matrices."""
        n = self.n_states
        m = self.n_controls
        N = self.N
        
        # Hessian for QP
        # H = G^T G + R (for unconstrained)
        # For constrained, use different formulation
        
        # Cost matrices
        self.Qt = np.zeros((N+1, n, n))
        for i in range(N):
            self.Qt[i] = self.Q
        self.Qt[N] = self.Q  # Terminal cost
        
        self.Rt = np.zeros((N, m, m))
        for i in range(N):
            self.Rt[i] = self.R
        
        # Prediction matrices
        # x_k = A^k x_0 + sum(A^(k-j) B u_j)
        self.M = np.zeros((N+1, n, n))
        self.M[0] = np.eye(n)
        for i in range(1, N+1):
            self.M[i] = self.A @ self.M[i-1]
        
        self.C = np.zeros((N+1, N, n, m))
        for i in range(N):
            for j in range(i+1):
                self.C[i, j] = self.M[i-j] @ self.B
        
        # Stacked matrices for QP
        self.H = np.zeros((N*m, N*m))
        for i in range(N):
            self.H[i*m:(i+1)*m, i*m:(i+1)*m] = self.Rt[i]
        
        self.F = np.zeros(((N+1)*n, N*m))
        for i in range(N):
            for j in range(i+1):
                self.F[i*n:(i+1)*n, j*m:(j+1)*m] = self.C[i, j]
    
    def solve(self, x0: np.ndarray, x_ref: np.ndarray) -> np.ndarray:
        """
        Solve MPC problem.
        
        Args:
            x0: Initial state
            x_ref: Reference trajectory (N+1 states)
            
        Returns:
            Optimal control sequence
        """
        N = self.N
        
        # Build reference vector
        x_ref_vec = np.zeros((N+1) * self.n_states)
        for i in range(min(N+1, len(x_ref))):
            x_ref_vec[i*self.n_states:(i+1)*self.n_states] = x_ref[i]
        
        # Cost: sum ||x_k - x_ref_k||^2 + ||u_k||^2
        # Minimize 0.5 u^T H u + x^T F^T u + const
        
        # Gradient
        g = self.F.T @ (self.M[0] @ x0 - x_ref_vec)
        
        # Solve unconstrained QP (use if no constraints)
        try:
            u = -np.linalg.solve(self.H + np.eye(N * self.n_controls) * 1e-6, g)
        except:
            u = np.zeros(N * self.n_controls)
        
        return u[:self.n_controls]
    
    def compute_control(self, x: np.ndarray, x_ref: np.ndarray) -> np.ndarray:
        """Compute first control input from MPC solution."""
        u = self.solve(x, x_ref)
        return u[:self.n_controls]
    
    def set_matrices(self, A: np.ndarray, B: np.ndarray):
        """Update system matrices."""
        self.A = A
        self.B = B
        self._build_mpc_matrices()


class QuadrotorMPCController:
    """
    Quadrotor-specific MPC controller.
    
    Uses nonlinear model with linearization.
    """
    
    def __init__(self, mass: float = 1.0, gravity: float = 9.81,
                 max_thrust: float = 25.0, max_rate: float = 5.0):
        """
        Initialize MPC controller.
        
        Args:
            mass, gravity: Physical parameters
            max_thrust: Maximum thrust (m/s^2)
            max_rate: Maximum angular rate (rad/s)
        """
        self.m = mass
        self.g = gravity
        self.max_thrust = max_thrust
        self.max_rate = max_rate
        
        self.horizon = 10
        self.dt = 0.1
        
        # State: [pos, vel, euler, rate]
        self.n_states = 12
        self.n_controls = 4  # [thrust, roll, pitch, yaw rate]
    
    def linearize(self, pos: np.ndarray, vel: np.ndarray,
                  euler: np.ndarray, omega: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Linearize quadrotor dynamics around operating point."""
        n = self.n_states
        m = self.n_controls
        
        A = np.zeros((n, n))
        
        # Position derivatives
        A[0:3, 3:6] = np.eye(3)
        
        # Velocity derivatives (simplified - depends on orientation)
        phi, theta, psi = euler
        
        # sin(roll) -> pitch coupling
        A[3, 6] = self.g * np.sin(theta)  # vx from roll
        A[4, 5] = -self.g * np.sin(phi)   # vy from pitch
        A[5, 4] = -self.g                  # vz from thrust (simplified)
        
        # Attitude derivatives
        A[6:9, 6:9] = np.eye(3) * 0  # Euler rate from Euler
        
        # Angular rate dynamics (identity for simplicity)
        A[9:12, 9:12] = -np.eye(3) * 0.5
        
        B = np.zeros((n, m))
        
        # Thrust effect on velocity
        B[5, 0] = 1.0 / self.m
        
        # Attitude effect on velocity
        B[3, 1] = self.g  # Roll
        B[4, 2] = self.g  # Pitch
        
        # Rate control
        B[9:12, 1:4] = np.eye(3)
        
        return A, B
    
    def predict(self, x0: np.ndarray, u_seq: np.ndarray) -> np.ndarray:
        """Predict state sequence from control sequence."""
        states = [x0]
        x = x0
        
        A, B = self.linearize(x0[:3], x0[3:6], x0[6:9], x0[9:12])
        
        for i, u in enumerate(u_seq):
            x = A @ x + B @ u
            states.append(x)
        
        return np.array(states)
    
    def optimize(self, x0: np.ndarray, x_ref: List[np.ndarray]) -> np.ndarray:
        """
        Optimize control sequence.
        
        Uses gradient descent with simple constraints.
        """
        N = self.horizon
        n_u = self.n_controls
        
        # Initial control sequence
        u_seq = np.zeros((N, n_u))
        
        # Cost weights
        Q_pos = 10.0
        Q_vel = 1.0
        Q_att = 5.0
        R_u = 0.1
        
        # Gradient descent iterations
        max_iter = 100
        lr = 0.1
        
        for _ in range(max_iter):
            # Predict states
            states = self.predict(x0, u_seq)
            
            # Compute gradient
            grad = np.zeros((N, n_u))
            
            for k in range(N):
                x_err = states[k] - x_ref[k] if k < len(x_ref) else states[k]
                
                # State error gradient w.r.t. control
                Q = np.diag([Q_pos, Q_pos, Q_pos, Q_vel, Q_vel, Q_vel,
                            Q_att, Q_att, Q_att, 1, 1, 1])
                
                A, B = self.linearize(states[k][:3], states[k][3:6], 
                                      states[k][6:9], states[k][9:12])
                
                # Simplified gradient
                grad[k] = R_u * u_seq[k] + B.T @ Q @ x_err[:12] * 0.01
            
            # Update control
            u_seq = u_seq - lr * grad
            
            # Apply constraints
            u_seq[:, 0] = np.clip(u_seq[:, 0], 0, self.max_thrust)  # Thrust
            u_seq[:, 1:] = np.clip(u_seq[:, 1:], -self.max_rate, self.max_rate)
        
        return u_seq[0]
    
    def compute_control(self, state: np.ndarray, ref: np.ndarray) -> np.ndarray:
        """Compute first control input."""
        ref_seq = [ref for _ in range(self.horizon + 1)]
        return self.optimize(state, ref_seq)