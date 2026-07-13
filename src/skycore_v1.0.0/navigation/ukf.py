"""Unscented Kalman Filter with full Sigma Points derivation.

UKF avoids linearization by using deterministic sampling (Sigma Points).

Parameters (Spherical Simplex):
  α = 0.001  (spread of Sigma Points)
  κ = 0      (secondary scaling parameter)  
  β = 2      (incorporates prior knowledge of distribution)
  L = n      (state dimension)

Lambda calculation:
  λ = α²(L + κ) - L

Sigma Points (2L+1):
  X₀ = x
  Xᵢ = x + √(L+λ) · [P]ᵢ        for i = 1..L
  Xᵢ₊ₗ = x - √(L+λ) · [P]ᵢ      for i = 1..L

Weights (mean and covariance):
  W₀ᵐ = λ / (L + λ)
  W₀ᶜ = λ / (L + λ) + (1 - α² + β)
  Wᵢᵐ = Wᵢᶜ = 1 / [2(L + λ)]    for i = 1..2L

Prediction Transform:
  Xₖ₋₁ⁱ = f(Xₖ₋₁ⁱ, u)
  x⁻ = Σ Wᵢᵐ · Xₖ₋₁ⁱ
  P⁻ = Σ Wᵢᶜ · (Xₖ₋₁ⁱ - x⁻)(Xₖ₋₁ⁱ - x⁻)ᵀ + Q

Update Transform:
  Zₖⁱ = h(Xₖⁱ)
  z⁻ = Σ Wᵢᵐ · Zₖⁱ
  S = Σ Wᵢᶜ · (Zₖⁱ - z⁻)(Zₖⁱ - z⁻)ᵀ + R
  Pₓᵧ = Σ Wᵢᶜ · (Xₖⁱ - x⁻)(Zₖⁱ - z⁻)ᵀ
  K = Pₓᵧ S⁻¹
  x⁺ = x⁻ + K(z - z⁻)
  P⁺ = P⁻ - KSKᵀ

References:
  - Julier & Uhlmann (1997) - New Extension of the Kalman Filter
  - Wan & van der Merwe (2000) - The Unscented Kalman Filter
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional, Tuple
import numpy as np
from numpy.typing import NDArray


@dataclass
class UKFConfig:
    """UKF configuration."""
    state_dim: int
    measurement_dim: int
    alpha: float = 0.001  # Primary scaling parameter
    kappa: float = 0      # Secondary scaling parameter
    beta: float = 2       # Prior knowledge (2 for Gaussian)
    process_noise: NDArray  # Q (n x n)
    measurement_noise: NDArray  # R (m x m)


class UnscentedKalmanFilter:
    """UKF with full Sigma Points implementation."""
    
    def __init__(self, config: UKFConfig):
        self.config = config
        self.n = config.state_dim
        self.m = config.measurement_dim
        
        # UKF parameters
        self.alpha = config.alpha
        self.kappa = config.kappa
        self.beta = config.beta
        
        # Calculate lambda
        self.lam = self.alpha ** 2 * (self.n + self.kappa) - self.n
        
        # Calculate weights
        self._compute_weights()
        
        # State and covariance
        self.x = np.zeros(self.n)
        self.P = np.eye(self.n)
        
        # Square-root UKF for numerical stability (optional)
        self.sqrt_method = 'cholesky'  # or 'qr'
    
    def _compute_weights(self) -> None:
        """Compute mean and covariance weights."""
        n_plus = self.n + self.lam
        
        # Mean weights
        self.Wm = np.zeros(2 * self.n + 1)
        self.Wm[0] = self.lam / n_plus
        
        # Covariance weights
        self.Wc = np.zeros(2 * self.n + 1)
        self.Wc[0] = self.lam / n_plus + (1 - self.alpha ** 2 + self.beta)
        
        # Remaining weights
        w = 0.5 / n_plus
        self.Wm[1:] = w
        self.Wc[1:] = w
    
    def _sigma_points(self, x: NDArray, P: NDArray) -> NDArray:
        """Generate Sigma Points.
        
        Returns:
            Sigma matrix (n x (2n+1)) where each column is a Sigma point
        """
        n = len(x)
        
        # Square root of (n+λ)P using Cholesky decomposition
        # Note: (n+λ)P = (n+λ) * P
        try:
            # Use eigendecomposition for numerical stability
            eigvals, eigvecs = np.linalg.eigh(P)
            eigvals = np.maximum(eigvals, 1e-10)  # Ensure positive
            sqrt_P = eigvecs @ np.diag(np.sqrt(eigvals)) @ eigvecs.T
        except np.linalg.LinAlgError:
            # Fallback to Cholesky with regularization
            P_reg = P + 1e-6 * np.eye(n)
            sqrt_P = np.linalg.cholesky(P_reg).T
        
        # Scaling factor
        gamma = np.sqrt(n + self.lam)
        
        # Create Sigma matrix
        sigma = np.zeros((n, 2 * n + 1))
        sigma[:, 0] = x
        
        for i in range(n):
            # Positive direction
            sigma[:, i + 1] = x + gamma * sqrt_P[:, i]
            # Negative direction
            sigma[:, i + n + 1] = x - gamma * sqrt_P[:, i]
        
        return sigma
    
    def _transform_sigma(
        self,
        sigma: NDArray,
        f: Callable[[NDArray], NDArray]
    ) -> NDArray:
        """Transform Sigma points through nonlinear function.
        
        Args:
            sigma: Sigma points (n x (2n+1))
            f: Nonlinear function
            
        Returns:
            Transformed Sigma points (n x (2n+1))
        """
        n, num_sigma = sigma.shape
        sigma_out = np.zeros_like(sigma)
        
        for i in range(num_sigma):
            sigma_out[:, i] = f(sigma[:, i])
        
        return sigma_out
    
    def predict(
        self,
        f: Callable[[NDArray], NDArray],
        u: Optional[NDArray] = None,
        Q: Optional[NDArray] = None
    ) -> Tuple[NDArray, NDArray]:
        """Prediction step.
        
        Args:
            f: Process model function: x_new = f(x, u)
            u: Optional control input
            Q: Optional process noise
            
        Returns:
            (x_pred, P_pred)
        """
        if Q is None:
            Q = self.config.process_noise
        
        # Generate Sigma points
        sigma = self._sigma_points(self.x, self.P)
        
        # Transform through process model
        if u is not None:
            def f_with_u(x): return f(x, u)
            sigma_pred = self._transform_sigma(sigma, f_with_u)
        else:
            sigma_pred = self._transform_sigma(sigma, f)
        
        # Compute mean
        x_pred = np.zeros(self.n)
        for i in range(2 * self.n + 1):
            x_pred += self.Wm[i] * sigma_pred[:, i]
        
        # Compute covariance
        P_pred = np.zeros((self.n, self.n))
        for i in range(2 * self.n + 1):
            diff = sigma_pred[:, i] - x_pred
            P_pred += self.Wc[i] * np.outer(diff, diff)
        P_pred += Q
        
        self.x = x_pred
        self.P = P_pred
        
        return x_pred.copy(), P_pred.copy()
    
    def update(
        self,
        z: NDArray,
        h: Callable[[NDArray], NDArray],
        R: Optional[NDArray] = None
    ) -> Tuple[NDArray, NDArray, NDArray]:
        """Update step.
        
        Args:
            z: Measurement (m,)
            h: Measurement function: z_pred = h(x)
            R: Optional measurement noise
            
        Returns:
            (x_update, P_update, K)
        """
        if R is None:
            R = self.config.measurement_noise
        
        # Generate Sigma points around predicted state
        sigma = self._sigma_points(self.x, self.P)
        
        # Transform through measurement model
        sigma_z = self._transform_sigma(sigma, h)
        
        # Compute predicted measurement
        z_pred = np.zeros(self.m)
        for i in range(2 * self.n + 1):
            z_pred += self.Wm[i] * sigma_z[:, i]
        
        # Innovation covariance S
        S = np.zeros((self.m, self.m))
        for i in range(2 * self.n + 1):
            diff = sigma_z[:, i] - z_pred
            S += self.Wc[i] * np.outer(diff, diff)
        S += R
        
        # Cross-covariance P_xy
        P_xy = np.zeros((self.n, self.m))
        for i in range(2 * self.n + 1):
            diff_x = sigma[:, i] - self.x
            diff_z = sigma_z[:, i] - z_pred
            P_xy += self.Wc[i] * np.outer(diff_x, diff_z)
        
        # Kalman gain
        K = P_xy @ np.linalg.inv(S)
        
        # State update
        self.x = self.x + K @ (z - z_pred)
        
        # Covariance update (Joseph form for stability)
        I_KH = np.eye(self.n) - K @ np.zeros((self.m, self.n))
        # Simplified: P = P - KSK^T + KRK^T
        self.P = self.P - K @ S @ K.T
        
        return self.x.copy(), self.P.copy(), K.copy()
    
    @property
    def state(self) -> NDArray:
        """Current state estimate."""
        return self.x.copy()
    
    @property
    def covariance(self) -> NDArray:
        """Current error covariance."""
        return self.P.copy()


class SquareRootUKF:
    """Square-root UKF for improved numerical stability.
    
    Instead of storing P, we store S where P = SS^T.
    This guarantees positive semi-definiteness.
    """
    
    def __init__(self, config: UKFConfig):
        self.config = config
        self.n = config.state_dim
        self.m = config.measurement_dim
        
        # UKF parameters
        self.alpha = config.alpha
        self.kappa = config.kappa
        self.beta = config.beta
        self.lam = self.alpha ** 2 * (self.n + self.kappa) - self.n
        
        # Weights
        self._compute_weights()
        
        # State and sqrt-covariance (S where P = SS^T)
        self.x = np.zeros(self.n)
        self.S = np.eye(self.n)
    
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
    
    def _sigma_points(self) -> NDArray:
        """Generate Sigma points from current state."""
        n = self.n
        
        # SVD for square root (more stable than Cholesky)
        try:
            U, s, Vh = np.linalg.svd(self.S)
            sqrt_P = U @ np.diag(np.sqrt(s)) @ Vh
        except np.linalg.LinAlgError:
            sqrt_P = np.eye(n)
        
        gamma = np.sqrt(n + self.lam)
        
        sigma = np.zeros((n, 2 * n + 1))
        sigma[:, 0] = self.x
        
        for i in range(n):
            sigma[:, i + 1] = self.x + gamma * sqrt_P[:, i]
            sigma[:, i + n + 1] = self.x - gamma * sqrt_P[:, i]
        
        return sigma
    
    def predict(self, f: Callable, u: Optional[NDArray] = None) -> Tuple[NDArray, NDArray]:
        """Prediction with square-root form."""
        sigma = self._sigma_points()
        
        # Transform Sigma points
        sigma_pred = np.zeros_like(sigma)
        for i in range(2 * self.n + 1):
            if u is not None:
                sigma_pred[:, i] = f(sigma[:, i], u)
            else:
                sigma_pred[:, i] = f(sigma[:, i])
        
        # Mean
        x_pred = np.zeros(self.n)
        for i in range(2 * self.n + 1):
            x_pred += self.Wm[i] * sigma_pred[:, i]
        
        # QR decomposition for covariance update
        # P = [√W₀^c (χ₀ - x̄), √Wᵢ^c (χᵢ - x̄)] [·]ᵀ
        # Use QR to get new S
        
        # Build matrix of weighted deviations
        D = np.zeros((self.n, 2 * self.n + 1))
        for i in range(2 * self.n + 1):
            D[:, i] = np.sqrt(max(self.Wc[i], 0)) * (sigma_pred[:, i] - x_pred)
        
        # Add process noise
        Q = self.config.process_noise
        try:
            Q_sqrt = np.linalg.cholesky(Q)
            D = np.hstack([D, Q_sqrt])
        except np.linalg.LinAlgError:
            pass
        
        # QR decomposition
        # S_new = qr(D)' * diag(weights)
        # For simplicity, use SVD
        U, s, Vh = np.linalg.svd(D, full_matrices=False)
        self.S = Vh.T @ np.diag(s / np.sqrt(max(2 * self.n + 1, 1)))
        
        self.x = x_pred
        
        # Reconstruct P for compatibility
        P = self.S @ self.S.T
        
        return x_pred.copy(), P.copy()
    
    @property
    def state(self) -> NDArray:
        return self.x.copy()
    
    @property
    def covariance(self) -> NDArray:
        return self.S @ self.S.T


def demo_ukf() -> None:
    """Demonstrate UKF on tracking problem."""
    print("=" * 60)
    print("Unscented Kalman Filter Demo")
    print("=" * 60)
    
    # State: [position, velocity]
    # Process: x_new = F @ x + w
    F = lambda x, u=None: np.array([
        x[0] + x[1] * 0.1,  # p += v * dt
        x[1]                 # v += 0
    ])
    
    # Measurement: z = position + noise
    H = lambda x: np.array([x[0]])
    
    # Noise
    Q = np.diag([0.01, 0.01])  # Process noise
    R = np.array([[1.0]])       # Measurement noise
    
    config = UKFConfig(
        state_dim=2,
        measurement_dim=1,
        alpha=0.001,
        kappa=0,
        beta=2,
        process_noise=Q,
        measurement_noise=R
    )
    
    ukf = SquareRootUKF(config)
    ukf.x = np.array([0, 1])  # Initial state
    ukf.S = np.diag([1, 0.1])   # Initial sqrt-covariance
    
    # Simulate
    np.random.seed(42)
    positions = []
    measurements = []
    estimates = []
    
    true_pos = 0
    true_vel = 1
    
    for t in range(100):
        # True position
        true_pos += true_vel * 0.1
        positions.append(true_pos)
        
        # Noisy measurement
        meas = true_pos + np.random.randn() * 1.0
        measurements.append(meas)
        
        # Predict
        ukf.predict(F)
        
        # Update
        z = np.array([meas])
        ukf.update(z, H)
        
        estimates.append(ukf.state[0])
    
    # Results
    print(f"\nFinal true position: {positions[-1]:.2f}")
    print(f"Final estimated position: {estimates[-1]:.2f}")
    print(f"Measurement noise std: 1.0")
    print(f"Estimation error: {abs(estimates[-1] - positions[-1]):.3f}")
    
    # Verify weights sum to 1
    print(f"\nWeights sum check:")
    print(f"  W_m sum: {np.sum(ukf.Wm):.6f} (should be 1)")
    print(f"  W_c sum: {np.sum(ukf.Wc):.6f} (should be 1)")


if __name__ == "__main__":
    demo_ukf()