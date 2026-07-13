"""
SkyCore PID Controller
======================
Proportional-Integral-Derivative control for drone stabilization.
"""

import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass
import logging

log = logging.getLogger(__name__)


@dataclass
class PIDConfig:
    """PID controller configuration."""
    kp: float = 1.0        # Proportional gain
    ki: float = 0.0        # Integral gain
    kd: float = 0.0        # Derivative gain
    min_output: float = -1.0  # Minimum output
    max_output: float = 1.0   # Maximum output
    min_integral: float = -0.5  # Anti-windup limit
    max_integral: float = 0.5


class PIDController:
    """
    PID Controller for drone control loops.
    
    Features:
    - Configurable gains
    - Anti-windup
    - Derivative filtering
    - Output saturation
    """
    
    def __init__(self, kp: float = 1.0, ki: float = 0.0, kd: float = 0.0,
                 config: Optional[PIDConfig] = None):
        """
        Initialize PID controller.
        
        Args:
            kp, ki, kd: PID gains
            config: PIDConfig for advanced settings
        """
        if config:
            self.kp = config.kp
            self.ki = config.ki
            self.kd = config.kd
            self.min_output = config.min_output
            self.max_output = config.max_output
            self.min_integral = config.min_integral
            self.max_integral = config.max_integral
        else:
            self.kp = kp
            self.ki = ki
            self.kd = kd
            self.min_output = -1.0
            self.max_output = 1.0
            self.min_integral = -0.5
            self.max_integral = 0.5
        
        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_derivative = 0.0
        
        # Derivative filter
        self.filter_alpha = 0.8  # Low-pass filter for derivative
        
        # D-term on measurement (not error) to avoid derivative kicks
        self.d_on_measurement = True
        
        self.last_time = None
    
    def compute(self, setpoint: float, measurement: float, dt: Optional[float] = None) -> float:
        """
        Compute PID output.
        
        Args:
            setpoint: Desired value
            measurement: Current measured value
            dt: Time step (seconds)
            
        Returns:
            Control output
        """
        error = setpoint - measurement
        
        # Calculate dt
        if dt is None:
            import time
            current_time = time.time()
            if self.last_time is None:
                dt = 0.01
            else:
                dt = current_time - self.last_time
            self.last_time = current_time
        else:
            self.last_time = None
        
        if dt <= 0:
            dt = 0.01
        
        # P term
        p_term = self.kp * error
        
        # I term with anti-windup
        self.integral += error * dt
        self.integral = np.clip(self.integral, self.min_integral, self.max_integral)
        i_term = self.ki * self.integral
        
        # D term with filtering
        if self.d_on_measurement:
            # D on measurement (no derivative kick on setpoint change)
            derivative = -measurement / dt
        else:
            derivative = error - self.prev_error / dt
        
        # Low-pass filter derivative
        filtered_derivative = self.filter_alpha * self.prev_derivative + (1 - self.filter_alpha) * derivative
        self.prev_derivative = filtered_derivative
        d_term = self.kd * filtered_derivative
        
        # Store error for next iteration
        self.prev_error = error
        
        # Total output
        output = p_term + i_term + d_term
        
        # Saturation
        output = np.clip(output, self.min_output, self.max_output)
        
        return output
    
    def compute_velocity(self, setpoint: float, measurement: float, dt: float) -> float:
        """Compute output with explicit dt for velocity control."""
        error = setpoint - measurement
        
        # P term
        p_term = self.kp * error
        
        # I term
        self.integral += error * dt
        self.integral = np.clip(self.integral, self.min_integral, self.max_integral)
        i_term = self.ki * self.integral
        
        # D term (on error)
        if dt > 0:
            derivative = (error - self.prev_error) / dt
        else:
            derivative = 0
        
        # Filter
        filtered_derivative = self.filter_alpha * self.prev_derivative + (1 - self.filter_alpha) * derivative
        d_term = self.kd * filtered_derivative
        
        self.prev_error = error
        self.prev_derivative = filtered_derivative
        
        output = p_term + i_term + d_term
        output = np.clip(output, self.min_output, self.max_output)
        
        return output
    
    def reset(self):
        """Reset controller state."""
        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_derivative = 0.0
    
    def set_gains(self, kp: float, ki: float, kd: float):
        """Update PID gains."""
        self.kp = kp
        self.ki = ki
        self.kd = kd
    
    def get_state(self) -> Dict:
        """Get controller state."""
        return {
            'integral': self.integral,
            'prev_error': self.prev_error,
            'kp': self.kp,
            'ki': self.ki,
            'kd': self.kd
        }
    
    @staticmethod
    def tune_rate(pid: 'PIDController', setpoint: float, measurement: float,
                 dt: float, iterations: int = 100) -> Dict:
        """
        Simple autotuning using Ziegler-Nichols method.
        
        Returns tuned gains.
        """
        # Increase Kp until oscillation
        kp = pid.kp
        while kp < 10.0:
            pid.set_gains(kp, 0, 0)
            
            # Simulate
            output = pid.compute_velocity(setpoint, measurement, dt)
            
            # Check if output oscillates
            if abs(output) > 0.8:
                break
            
            kp += 0.1
        
        # Record ultimate gain and period
        ku = kp
        pu = 0.1  # Placeholder period
        
        # Ziegler-Nichols tuning
        kp_tuned = 0.6 * ku
        ki_tuned = 1.2 * ku / pu
        kd_tuned = 0.6 * ku * pu
        
        return {
            'kp': kp_tuned,
            'ki': ki_tuned,
            'kd': kd_tuned
        }


class PIDControllerGroup:
    """Group of PID controllers for multi-axis control."""
    
    def __init__(self, num_axis: int = 3):
        """Initialize controller group."""
        self.controllers = [
            PIDController() for _ in range(num_axis)
        ]
    
    def compute_all(self, setpoints: np.ndarray, measurements: np.ndarray, dt: float) -> np.ndarray:
        """Compute outputs for all axes."""
        outputs = np.zeros(len(self.controllers))
        for i, (setpoint, measurement, controller) in enumerate(
            zip(setpoints, measurements, self.controllers)
        ):
            outputs[i] = controller.compute_velocity(setpoint, measurement, dt)
        return outputs
    
    def reset_all(self):
        """Reset all controllers."""
        for controller in self.controllers:
            controller.reset()
    
    def set_gains_all(self, kp: float, ki: float, kd: float):
        """Set same gains for all controllers."""
        for controller in self.controllers:
            controller.set_gains(kp, ki, kd)
    
    def set_gains_individual(self, gains: list):
        """Set individual gains for each controller."""
        for controller, gain in zip(self.controllers, gains):
            if len(gain) == 3:
                controller.set_gains(gain[0], gain[1], gain[2])