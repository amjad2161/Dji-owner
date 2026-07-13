"""LQR Controller (Linear Quadratic Regulator).

Implements infinite-horizon discrete LQR with algebraic Riccati equation solver.

Cost function:
  J = Σ (x^T Q x + u^T R u)
  
Constraint:
  x_{k+1} = A x_k + B u_k

Solution via algebraic Riccati equation:
  P = Q + A^T P A - A^T P B (R + B^T P B)^{-1} B^T P A
  
LQR gain:
  K = -(R + B^T P B)^{-1} B^T P A
  u = K x

References:
  - Anderson & Moore (1989) - Optimal Control
  - Bertsekas (2005) - Dynamic Programming and Optimal Control
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
from numpy.typing import NDArray


@dataclass
class LQRConfig:
    """LQR controller configuration."""
    A: NDArray  # State transition matrix (n x n)
    B: NDArray  # Control matrix (n x m)
    Q: NDArray  # State cost matrix (n x n), positive semidefinite
    R: NDArray  # Control cost matrix (m x m), positive definite
    
    # Optional: constrain final state
    Qf: Optional[NDArray] = None  # Terminal cost
    
    # Convergence tolerance
    tol: float = 1e-9
    max_iter: int = 1000


class LQRController:
    """Infinite-horizon discrete LQR controller."""
    
    def __init__(self, config: Optional[LQRConfig] = None):
        self.config = config
        
        if config is not None:
            self.n, self.m = config.B.shape
            self.K = None
            self.P = None
            self._compute_gains()
    
    def _compute_gains(self) -> None:
        """Solve algebraic Riccati equation iteratively."""
        A, B, Q, R = self.config.A, self.config.B, self.config.Q, self.config.R
        n, m = B.shape
        
        # Initial P = Q
        P = Q.copy()
        
        for iteration in range(self.config.max_iter):
            # Riccati iteration
            # P_new = Q + A^T P A - A^T P B (R + B^T P B)^{-1} B^T P A
            
            # Compute BP = B^T @ P
            BP = B.T @ P
            
            # Compute M = R + B^T @ P @ B
            M = R + BP @ B
            
            # Check if M is invertible
            try:
                M_inv = np.linalg.inv(M)
            except np.linalg.LinAlgError:
                # Add regularization
                M = M + 1e-6 * np.eye(m)
                M_inv = np.linalg.inv(M)
            
            # Update P
            AB = A.T @ (P - P @ B @ M_inv @ BP)
            P_new = Q + AB @ A
            
            # Check convergence
            diff = np.max(np.abs(P_new - P))
            P = P_new
            
            if diff < self.config.tol:
                print(f"LQR converged after {iteration + 1} iterations")
                break
        
        self.P = P
        
        # Compute LQR gain
        # K = -(R + B^T P B)^{-1} B^T P A
        self.K = -M_inv @ (B.T @ P @ A)
    
    @property
    def gain(self) -> NDArray:
        """LQR gain matrix K."""
        return self.K.copy()
    
    @property
    def Riccati_solution(self) -> NDArray:
        """Solution to Riccati equation P."""
        return self.P.copy()
    
    def compute(self, x: NDArray) -> NDArray:
        """Compute control input.
        
        Args:
            x: State vector (n,)
            
        Returns:
            u: Control input (m,)
        """
        if self.K is None:
            raise RuntimeError("LQR not initialized. Call _compute_gains() first.")
        
        return self.K @ x
    
    def compute_with_feedforward(self, x: NDArray, u_ff: NDArray) -> NDArray:
        """Compute control with feedforward term.
        
        Args:
            x: State vector (n,)
            u_ff: Feedforward control (m,)
            
        Returns:
            u: Total control input
        """
        return self.K @ x + u_ff
    
    def verify_stability(self) -> Tuple[bool, float]:
        """Verify closed-loop stability.
        
        Returns:
            (is_stable, max_eigenvalue)
        """
        A_cl = self.config.A + self.config.B @ self.K
        eigenvalues = np.linalg.eigvals(A_cl)
        max_eigen = np.max(np.abs(eigenvalues))
        
        is_stable = max_eigen < 1.0
        
        return is_stable, max_eigen
    
    def gain_scheduling(self, x: NDArray) -> Tuple[NDArray, bool]:
        """Compute gain-scheduled control.
        
        For nonlinear systems, use local linearization.
        
        Args:
            x: Current state
            
        Returns:
            (u, gain_changed): Control and whether gain was updated
        """
        # In this simple implementation, gain is constant
        # For true gain scheduling, would need multiple LQR controllers
        return self.compute(x), False


def demo_lqr():
    """Demonstrate LQR controller."""
    print("=" * 60)
    print("LQR Controller Demo")
    print("=" * 60)
    
    # Simple double integrator: x1_dot = x2, x2_dot = u
    # Discrete: x1_{k+1} = x1_k + dt*x2_k, x2_{k+1} = x2_k + dt*u_k
    
    dt = 0.1
    A = np.array([
        [1, dt],
        [0, 1]
    ])
    B = np.array([[0], [dt]])
    
    # Cost matrices
    Q = np.diag([10, 1])  # Penalize position more than velocity
    R = np.diag([0.1])   # Penalize control effort
    
    config = LQRConfig(A=A, B=B, Q=Q, R=R)
    
    lqr = LQRController(config)
    
    print(f"\nLQR gain matrix K:\n{lqr.K}")
    print(f"\nRiccati solution P:\n{lqr.P}")
    
    # Verify stability
    is_stable, max_eig = lqr.verify_stability()
    print(f"\nClosed-loop stability: {is_stable} (max |λ| = {max_eig:.4f})")
    
    # Simulate
    print("\n" + "=" * 40)
    print("Simulating tracking...")
    print("=" * 40)
    
    x = np.array([10, 0])  # Initial state: position = 10
    positions = [x[0]]
    
    for t in range(100):
        u = lqr.compute(x)
        x = A @ x + B @ u.flatten()
        positions.append(x[0])
        
        if t % 20 == 0:
            print(f"  t={t*dt:.1f}s: pos={x[0]:.3f}, vel={x[1]:.3f}, u={u[0]:.3f}")
    
    print(f"\nFinal position: {positions[-1]:.4f}")
    print(f"Final velocity: {x[1]:.4f}")
    
    # Test with setpoint tracking
    print("\n" + "=" * 40)
    print("Setpoint tracking: reference = 5")
    print("=" * 40)
    
    # Augment state for setpoint tracking: x_aug = [e; ref]
    # For simplicity, just shift the equilibrium
    
    x = np.array([5, 0])  # Start at setpoint
    for t in range(50):
        u = lqr.compute(x)
        x = A @ x + B @ u.flatten()
        
        if t % 10 == 0:
            print(f"  t={t*dt:.1f}s: pos={x[0]:.3f}, u={u[0]:.3f}")
    
    print(f"\nFinal position: {x[0]:.4f} (setpoint: 5)")


if __name__ == "__main__":
    demo_lqr()