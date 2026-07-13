"""Kalman Filter — n-dimensional with full Gaussian derivation.

Derivation from conditional Gaussian:
  p(x_k | z_{1:k}) = N(x_k; μ_{x|z}, Σ_{x|z})
  
  Conditional distribution parameters:
    μ_{x|z} = μ_x + Σ_{xz} Σ_{zz}^{-1} (z - μ_z)
    Σ_{x|z} = Σ_{xx} - Σ_{xz} Σ_{zz}^{-1} Σ_{zx}

For linear Gaussian system:
  x_k = F_k x_{k-1} + B_k u_{k-1} + w_k,  w_k ~ N(0, Q_k)
  z_k = H_k x_k + v_k,                       v_k ~ N(0, R_k)

Prediction step:
  x_pred = F x_prev + B u
  P_pred = F P_prev F^T + Q

Update step (from conditional Gaussian):
  K = P_pred H^T (H P_pred H^T + R)^{-1}
  x_update = x_pred + K (z - H x_pred)
  P_update = (I - K H) P_pred

References:
  - Kalman (1960) - New Approach to Linear Filtering
  - Maybeck (1979) - Stochastic Models, Estimation, and Control, Vol.1
  - Bar-Shalom et al. (2001) - Estimation with Applications to Tracking
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Callable
import numpy as np
from numpy.typing import NDArray


@dataclass
class KalmanConfig:
    """Kalman filter configuration."""
    state_dim: int
    measurement_dim: int
    F: NDArray  # State transition matrix (n x n)
    H: NDArray  # Measurement matrix (m x n)
    Q: NDArray  # Process noise covariance (n x n)
    R: NDArray  # Measurement noise covariance (m x m)
    B: Optional[NDArray] = None  # Control matrix (n x r), None if no control
    x0: Optional[NDArray] = None  # Initial state
    P0: Optional[NDArray] = None  # Initial covariance


class KalmanFilter:
    """n-dimensional Kalman Filter with full formulas."""
    
    def __init__(self, config: KalmanConfig):
        self.config = config
        self.n = config.state_dim
        self.m = config.measurement_dim
        
        # Initialize state
        if config.x0 is not None:
            self.x = config.x0.copy()
        else:
            self.x = np.zeros(self.n)
        
        # Initialize covariance
        if config.P0 is not None:
            self.P = config.P0.copy()
        else:
            self.P = np.eye(self.n)
        
        # Innovation tracking for adaptive Q
        self.innovation_history: list[NDArray] = []
        self.adaptive_q_enabled = False
        self.adaptive_lambda = 0.01  # Forgetting factor
    
    @property
    def state(self) -> NDArray:
        """Current state estimate."""
        return self.x.copy()
    
    @property
    def covariance(self) -> NDArray:
        """Current error covariance."""
        return self.P.copy()
    
    def predict(self, u: Optional[NDArray] = None) -> tuple[NDArray, NDArray]:
        """Prediction step.
        
        Computes:
          x_pred = F x + B u
          P_pred = F P F^T + Q
        
        Args:
            u: Control input vector (r,). If None, uses zero control.
            
        Returns:
            (x_pred, P_pred): Predicted state and covariance
        """
        F, B, Q = self.config.F, self.config.B, self.config.Q
        x, P = self.x, self.P
        
        # State prediction
        if B is not None and u is not None:
            self.x = F @ x + B @ u
        else:
            self.x = F @ x
        
        # Covariance prediction (discrete-time Riccati)
        self.P = F @ P @ F.T + Q
        
        return self.x.copy(), self.P.copy()
    
    def update(self, z: NDArray) -> tuple[NDArray, NDArray, NDArray]:
        """Update step using conditional Gaussian derivation.
        
        Innovation: ν = z - H x_pred
        Kalman gain: K = P_pred H^T (H P_pred H^T + R)^{-1}
        State update: x = x_pred + K ν
        Covariance update: P = (I - K H) P_pred
        
        Args:
            z: Measurement vector (m,)
            
        Returns:
            (x, P, K): Updated state, covariance, and gain
        """
        H, R = self.config.H, self.config.R
        x_pred, P_pred = self.x.copy(), self.P.copy()
        
        # Innovation
        nu = z - H @ x_pred
        self.innovation_history.append(nu)
        
        # Innovation covariance (S)
        S = H @ P_pred @ H.T + R
        
        # Kalman gain (from conditional Gaussian derivation)
        # K = P_pred H^T S^{-1}
        K = P_pred @ H.T @ np.linalg.inv(S)
        
        # State update
        self.x = x_pred + K @ nu
        
        # Covariance update (Joseph form for numerical stability)
        I_KH = np.eye(self.n) - K @ H
        self.P = I_KH @ P_pred @ I_KH.T + K @ R @ K.T
        
        # Adaptive Q if enabled
        if self.adaptive_q_enabled:
            self._adapt_Q(nu, K)
        
        return self.x.copy(), self.P.copy(), K.copy()
    
    def _adapt_Q(self, innovation: NDArray, K: NDArray) -> None:
        """Adaptive process noise estimation.
        
        Q_k = (1-λ) Q_{k-1} + λ K ν ν^T K^T
        
        Args:
            innovation: Innovation vector ν
            K: Kalman gain
        """
        lambda_k = self.adaptive_lambda
        self.config.Q = (
            (1 - lambda_k) * self.config.Q +
            lambda_k * K @ innovation @ innovation.T @ K.T
        )
    
    def step(self, z: NDArray, u: Optional[NDArray] = None) -> tuple[NDArray, NDArray]:
        """Combined predict-update step.
        
        Args:
            z: Measurement
            u: Optional control input
            
        Returns:
            (x, P): Updated state and covariance
        """
        self.predict(u)
        x, P, _ = self.update(z)
        return x, P
    
    def enable_adaptive_Q(self, lambda_: float = 0.01) -> None:
        """Enable adaptive process noise estimation.
        
        Args:
            lambda_: Forgetting factor (0 < λ << 1)
        """
        self.adaptive_q_enabled = True
        self.adaptive_lambda = lambda_
    
    def reset(self, x0: Optional[NDArray] = None, P0: Optional[NDArray] = None) -> None:
        """Reset filter to initial state.
        
        Args:
            x0: New initial state (n,), uses zero if None
            P0: New initial covariance (n,n), uses identity if None
        """
        if x0 is not None:
            self.x = x0.copy()
        else:
            self.x = np.zeros(self.n)
        
        if P0 is not None:
            self.P = P0.copy()
        else:
            self.P = np.eye(self.n)
        
        self.innovation_history.clear()
    
    def innovation_whiteness(self, window: int = 100) -> float:
        """Check innovation whiteness (multipath detection).
        
        Returns:
            Normalized innovation squared (should be ~m for white innovation)
        """
        if len(self.innovation_history) < 2:
            return 0.0
        
        innovations = np.array(self.innovation_history[-window:])
        return np.mean(np.sum(innovations ** 2, axis=1))


class ScalarKalmanFilter:
    """1D Kalman filter for demonstration."""
    
    def __init__(
        self,
        x0: float = 0.0,
        P0: float = 1.0,
        F: float = 1.0,
        H: float = 1.0,
        Q: float = 0.01,
        R: float = 0.1
    ):
        """Initialize scalar Kalman filter.
        
        Args:
            x0: Initial state
            P0: Initial variance
            F: State transition (x_new = F * x)
            H: Measurement matrix (z = H * x)
            Q: Process noise variance
            R: Measurement noise variance
        """
        self.x = x0
        self.P = P0
        self.F = F
        self.H = H
        self.Q = Q
        self.R = R
    
    def predict(self) -> tuple[float, float]:
        """Prediction step."""
        self.x = self.F * self.x
        self.P = self.F * self.P * self.F + self.Q
        return self.x, self.P
    
    def update(self, z: float) -> tuple[float, float, float]:
        """Update step."""
        # Innovation
        nu = z - self.H * self.x
        
        # Kalman gain
        S = self.H * self.P * self.H + self.R
        K = self.P * self.H / S
        
        # Update
        self.x = self.x + K * nu
        self.P = (1 - K * self.H) * self.P
        
        return self.x, self.P, K
    
    def step(self, z: float) -> tuple[float, float]:
        """Combined predict-update."""
        self.predict()
        return self.update(z)


def demo_1d_tracking() -> None:
    """Demonstrate Kalman filter on 1D position tracking with noise."""
    print("=" * 60)
    print("Kalman Filter Demo: 1D Position Tracking")
    print("=" * 60)
    
    # True position starts at 0, moves at constant velocity
    dt = 0.1
    true_pos = 0.0
    true_vel = 1.0
    positions = []
    measurements = []
    
    # Generate true trajectory and noisy measurements
    np.random.seed(42)
    for t in range(100):
        true_pos += true_vel * dt
        positions.append(true_pos)
        
        # Add measurement noise (std=0.5)
        meas = true_pos + np.random.randn() * 0.5
        measurements.append(meas)
    
    # Kalman filter for position tracking
    # State: [position, velocity]
    F = np.array([[1, dt], [0, 1]])
    H = np.array([[1, 0]])
    Q = np.array([[0.01, 0], [0, 0.01]])  # Process noise
    R = np.array([[0.5 ** 2]])  # Measurement noise
    
    kf = KalmanFilter(
        KalmanConfig(
            state_dim=2,
            measurement_dim=1,
            F=F,
            H=H,
            Q=Q,
            R=R,
            x0=np.array([0, 1]),  # Initial [pos, vel]
            P0=np.diag([1, 0.1])
        )
    )
    
    # Track
    estimates = []
    for z in measurements:
        kf.predict()
        x, P, K = kf.update(z)
        estimates.append(x[0])
    
    # Results
    print(f"\nTrue final position: {positions[-1]:.2f}")
    print(f"Estimated final position: {estimates[-1]:.2f}")
    print(f"Measurement noise std: 0.5")
    print(f"Final estimation error: {abs(estimates[-1] - positions[-1]):.3f}")
    
    # Innovation whiteness (should be close to m=1 for white innovation)
    whiteness = kf.innovation_whiteness()
    print(f"Innovation whiteness: {whiteness:.2f} (should be ~1.0)")


if __name__ == "__main__":
    demo_1d_tracking()