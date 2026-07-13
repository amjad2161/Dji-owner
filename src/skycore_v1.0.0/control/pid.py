"""PID Controller with anti-windup and gain scheduling.

Implements standard PID, PI-D, I-PD variants with multiple anti-windup methods.

Equations:

Standard PID: u(t) = Kp e(t) + Ki ∫e(t)dt + Kd de(t)/dt

PI-D (derivative on measurement):
  u = Kp e + Ki ∫e dt + Kd (-dm/dt)
  where m is measured output, e = r - m

I-PD (proportional on measurement):
  u = Kp (-m) + Ki ∫e dt + Kd (-dm/dt)

Anti-windup methods:
  1. Conditional integration: only integrate when |u| < u_max
  2. Back-calculation: u_lim = Kp e + Ki ∫e dt - Kd de/dt + Kt (u - u_lim)
     where Kt is tracking gain

Bumpless transfer: ensures smooth transition when switching modes.

Reference: Åström and Hägglund (1995) - PID Controllers
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Callable
import numpy as np
from numpy.typing import NDArray


@dataclass
class PIDConfig:
    """PID controller configuration."""
    kp: float = 1.0           # Proportional gain
    ki: float = 0.0           # Integral gain
    kd: float = 0.0           # Derivative gain
    u_min: float = -100.0     # Minimum output
    u_max: float = 100.0      # Maximum output
    rate_limit: float = 1000.0 # Maximum output rate (units/sec)
    derivative_filter_tau: float = 0.0  # Derivative filter time constant
    anti_windup: str = "conditional"  # "conditional" or "back_calc"
    tracking_gain: float = 1.0  # For back-calculation
    bumpless: bool = True       # Enable bumpless transfer


class PIDController:
    """PID controller with variants and anti-windup."""
    
    def __init__(self, config: Optional[PIDConfig] = None):
        self.config = config or PIDConfig()
        
        # Gains
        self.kp = self.config.kp
        self.ki = self.config.ki
        self.kd = self.config.kd
        
        # State
        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_measurement = 0.0
        self.prev_output = 0.0
        self.prev_time = None
        self.derivative_filtered = 0.0
        
        # For bumpless transfer
        self._initialized = False
    
    def reset(self) -> None:
        """Reset controller state."""
        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_measurement = 0.0
        self.prev_output = 0.0
        self.prev_time = None
        self.derivative_filtered = 0.0
        self._initialized = False
    
    def set_gains(self, kp: float, ki: float, kd: float) -> None:
        """Update PID gains."""
        self.kp = kp
        self.ki = ki
        self.kd = kd
    
    def compute(
        self,
        measurement: float,
        setpoint: float,
        time: Optional[float] = None,
        measurement_dot: Optional[float] = None
    ) -> float:
        """Compute PID output.
        
        Args:
            measurement: Current measured value
            setpoint: Desired setpoint
            time: Current time (for rate limiting)
            measurement_dot: External derivative measurement (optional)
            
        Returns:
            u: Control output
        """
        # Error
        error = setpoint - measurement
        
        # Time step
        if time is not None and self.prev_time is not None:
            dt = time - self.prev_time
            dt = max(dt, 1e-6)  # Prevent division by zero
        else:
            dt = 0.01  # Assume 100Hz
            self.prev_time = time
        
        # Initialize on first call (for bumpless transfer)
        if not self._initialized:
            self.prev_error = error
            self.prev_measurement = measurement
            self._initialized = True
        
        # Integral term (with anti-windup)
        integral_new = self.integral + error * dt
        
        # Proportional term
        u_p = self.kp * error
        
        # Derivative term
        if measurement_dot is not None:
            # Use external derivative (e.g., from encoder)
            derivative = -measurement_dot
        else:
            # Numerical derivative with filtering
            if dt > 0:
                raw_derivative = (error - self.prev_error) / dt
                
                # Apply first-order filter: tau * dD/dt + D = D_raw
                # D_filtered = alpha * D_raw + (1-alpha) * D_prev
                if self.config.derivative_filter_tau > 0:
                    alpha = dt / (self.config.derivative_filter_tau + dt)
                    derivative = alpha * raw_derivative + (1 - alpha) * self.derivative_filtered
                    self.derivative_filtered = derivative
                else:
                    derivative = raw_derivative
        
        u_d = self.kd * derivative
        
        # Combine
        u = u_p + self.ki * integral_new + u_d
        
        # Anti-windup
        if self.config.anti_windup == "conditional":
            # Conditional integration: only integrate if output not saturated
            if u > self.config.u_max:
                integral_new = (self.config.u_max - u_p - u_d) / max(self.ki, 1e-9)
            elif u < self.config.u_min:
                integral_new = (self.config.u_min - u_p - u_d) / max(self.ki, 1e-9)
            self.integral = integral_new
            u = u_p + self.ki * self.integral + u_d
            
        elif self.config.anti_windup == "back_calc":
            # Back-calculation anti-windup
            if u > self.config.u_max:
                # Reduce integral to bring output within limits
                back_calc = self.config.tracking_gain * (u - self.config.u_max)
                self.integral -= back_calc * dt
            elif u < self.config.u_min:
                back_calc = self.config.tracking_gain * (self.config.u_min - u)
                self.integral -= back_calc * dt
        
        # Rate limiting
        if self.prev_output is not None:
            max_change = self.config.rate_limit * dt
            u = np.clip(u, self.prev_output - max_change, self.prev_output + max_change)
        
        # Final saturation
        u = np.clip(u, self.config.u_min, self.config.u_max)
        
        # Update state
        self.prev_error = error
        self.prev_measurement = measurement
        self.prev_output = u
        if time is not None:
            self.prev_time = time
        
        return u
    
    def compute_pid(
        self,
        measurement: float,
        setpoint: float,
        time: Optional[float] = None
    ) -> float:
        """Standard PID: derivative on error."""
        return self.compute(measurement, setpoint, time)
    
    def compute_pi_d(
        self,
        measurement: float,
        setpoint: float,
        time: Optional[float] = None,
        measurement_dot: Optional[float] = None
    ) -> float:
        """PI-D: derivative on measurement to reduce noise."""
        return self.compute(measurement, setpoint, time, -measurement_dot if measurement_dot is None else measurement_dot)
    
    def compute_i_pd(
        self,
        measurement: float,
        setpoint: float,
        time: Optional[float] = None,
        measurement_dot: Optional[float] = None
    ) -> float:
        """I-PD: proportional on measurement, derivative on measurement."""
        error = setpoint - measurement
        
        # Time
        if time is not None and self.prev_time is not None:
            dt = time - self.prev_time
            dt = max(dt, 1e-6)
        else:
            dt = 0.01
        
        if not self._initialized:
            self.prev_measurement = measurement
            self._initialized = True
        
        # Integral of error
        self.integral += error * dt
        
        # Anti-windup
        u_i = self.ki * self.integral
        if u_i > self.config.u_max:
            self.integral = self.config.u_max / max(self.ki, 1e-9)
        elif u_i < self.config.u_min:
            self.integral = self.config.u_min / max(self.ki, 1e-9)
        
        # Proportional on measurement (negative feedback)
        u_p = -self.kp * measurement
        
        # Derivative on measurement
        if measurement_dot is not None:
            derivative = measurement_dot
        else:
            if time is not None:
                dt = time - self.prev_time if self.prev_time else 0.01
                derivative = (measurement - self.prev_measurement) / max(dt, 1e-6)
            else:
                derivative = 0
        
        u_d = -self.kd * derivative
        
        # Combine
        u = u_p + u_i + u_d
        
        # Saturation
        u = np.clip(u, self.config.u_min, self.config.u_max)
        
        # Rate limiting
        if self.prev_output is not None:
            max_change = self.config.rate_limit * dt
            u = np.clip(u, self.prev_output - max_change, self.prev_output + max_change)
        
        # Update
        self.prev_measurement = measurement
        self.prev_output = u
        if time is not None:
            self.prev_time = time
        
        return u


class GainScheduler:
    """Gain scheduling for PID controllers across flight phases."""
    
    def __init__(self):
        # Schedule: {phase: PIDConfig}
        self.schedules: dict[str, list[tuple[float, PIDConfig]]] = {}
        self.current_phase = None
    
    def add_schedule(
        self,
        phase: str,
        schedule: list[tuple[float, PIDConfig]]
    ) -> None:
        """Add gain schedule for a phase.
        
        Args:
            phase: Phase name (e.g., "hover", "cruise")
            schedule: List of (velocity_threshold, PIDConfig)
        """
        self.schedules[phase] = sorted(schedule, key=lambda x: x[0])
    
    def get_gains(self, phase: str, velocity: float) -> PIDConfig:
        """Get interpolated gains for current velocity."""
        if phase not in self.schedules:
            # Return default
            return PIDConfig()
        
        schedule = self.schedules[phase]
        
        # Find appropriate gains by interpolation
        v_prev, config_prev = schedule[0]
        
        for v_next, config_next in schedule[1:]:
            if velocity <= v_next:
                # Linear interpolation
                if v_next == v_prev:
                    return config_prev
                t = (velocity - v_prev) / (v_next - v_prev)
                return PIDConfig(
                    kp=config_prev.kp + t * (config_next.kp - config_prev.kp),
                    ki=config_prev.ki + t * (config_next.ki - config_prev.ki),
                    kd=config_prev.kd + t * (config_next.kd - config_prev.kd),
                    u_min=config_prev.u_min,
                    u_max=config_prev.u_max
                )
            v_prev, config_prev = v_next, config_next
        
        return config_prev


def demo_pid():
    """Demonstrate PID controller."""
    print("=" * 60)
    print("PID Controller Demo")
    print("=" * 60)
    
    # Position controller
    config = PIDConfig(kp=10, ki=1, kd=5, u_max=100, derivative_filter_tau=0.01)
    pid = PIDController(config)
    
    # Simulate tracking a setpoint
    dt = 0.01
    setpoint = 10.0
    position = 0.0
    velocity = 0.0
    
    print(f"\nTracking setpoint: {setpoint}m")
    print(f"Initial position: {position}m")
    
    positions = []
    outputs = []
    
    for t in range(1000):
        # Simple dynamics: m_dot = u
        measurement = position
        
        u = pid.compute(measurement, setpoint, t * dt)
        
        velocity += u * dt
        position += velocity * dt
        
        positions.append(position)
        outputs.append(u)
        
        if t % 200 == 0:
            print(f"  t={t*dt:.1f}s: pos={position:.3f}, vel={velocity:.3f}, u={u:.3f}")
    
    print(f"\nFinal position: {positions[-1]:.3f}m (setpoint: {setpoint}m)")
    print(f"Steady-state error: {abs(positions[-1] - setpoint):.6f}m")
    
    # Test anti-windup
    print("\n" + "=" * 40)
    print("Anti-windup Test (with output saturation)")
    print("=" * 40)
    
    config_sat = PIDConfig(kp=20, ki=5, kd=2, u_max=10)  # Limited output
    pid_sat = PIDController(config_sat)
    
    position = 0
    for t in range(500):
        u = pid_sat.compute(position, 20, t * dt)
        position += u * dt * 0.1
        
        if t % 100 == 0:
            print(f"  t={t*dt:.1f}s: pos={position:.2f}, u={u:.2f}, integral={pid_sat.integral:.4f}")


if __name__ == "__main__":
    demo_pid()