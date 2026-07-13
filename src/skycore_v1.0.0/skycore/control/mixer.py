"""
SkyCore Motor Mixer
==================
Maps control inputs to motor outputs for different frame types.
"""

import numpy as np
from typing import Tuple, List
import logging

log = logging.getLogger(__name__)


class MotorMixer:
    """
    Motor mixer for quadrotor control.
    
    Converts desired thrust and moments to motor PWM values.
    Supports multiple frame configurations.
    """
    
    FRAME_TYPES = {
        'quad_x': {
            'motors': 4,
            'config': [
                # (thrust_dir, roll_dir, pitch_dir, yaw_dir)
                (1, -1,  1, -1),  # Front right (CW)
                (1,  1, -1, -1),  # Front left (CCW)
                (1,  1,  1,  1),  # Back left (CW)
                (1, -1, -1,  1),  # Back right (CCW)
            ],
            'prop_dir': [1, -1, 1, -1]  # CW/CCW for yaw
        },
        'quad_plus': {
            'motors': 4,
            'config': [
                (1,  0, -1,  1),  # Front
                (1,  1,  0, -1),  # Right
                (1,  0,  1,  1),  # Back
                (1, -1,  0, -1),  # Left
            ],
            'prop_dir': [1, -1, 1, -1]
        },
        'hexa_x': {
            'motors': 6,
            'config': [
                (1, -0.5,  0.866, -1),
                (1, -0.5, -0.866,  1),
                (1,  0,    0,    -1),
                (1,  0,    0,     1),
                (1,  0.5, -0.866, -1),
                (1,  0.5,  0.866,  1),
            ],
            'prop_dir': [1, -1, 1, -1, 1, -1]
        },
        'octa_x': {
            'motors': 8,
            'config': [
                (1, -0.707,  0.707, -1),
                (1,  0,      1,     -1),
                (1,  0.707,  0.707,  1),
                (1,  1,      0,      1),
                (1,  0.707, -0.707, -1),
                (1,  0,     -1,      1),
                (1, -0.707, -0.707,  1),
                (1, -1,      0,     -1),
            ],
            'prop_dir': [1, -1, 1, -1, 1, -1, 1, -1]
        }
    }
    
    def __init__(self, frame_type: str = 'quad_x', 
                 min_pwm: float = 1000, max_pwm: float = 2000):
        """
        Initialize motor mixer.
        
        Args:
            frame_type: Frame configuration
            min_pwm, max_pwm: PWM range
        """
        self.frame_type = frame_type
        
        if frame_type not in self.FRAME_TYPES:
            log.warning(f"Unknown frame type {frame_type}, using quad_x")
            frame_type = 'quad_x'
        
        config = self.FRAME_TYPES[frame_type]
        self.n_motors = config['motors']
        self.motor_config = np.array(config['config'])
        self.prop_dir = np.array(config['prop_dir'])
        
        self.min_pwm = min_pwm
        self.max_pwm = max_pwm
        self.mid_pwm = (min_pwm + max_pwm) / 2
        
        # Motor limits
        self.min_thrust = 0.0
        self.max_thrust = 1.0
    
    def mix(self, thrust: float, roll: float, pitch: float, yaw: float) -> np.ndarray:
        """
        Convert control inputs to motor outputs.
        
        Args:
            thrust: Total thrust (0-1)
            roll: Roll moment (-1 to 1)
            pitch: Pitch moment (-1 to 1)
            yaw: Yaw moment (-1 to 1)
            
        Returns:
            Motor PWM values (array of n_motors)
        """
        # Control vector
        u = np.array([thrust, roll, pitch, yaw])
        
        # Motor outputs (before clipping)
        motor_outputs = self.motor_config @ u
        
        # Normalize to 0-1 range
        motor_outputs = (motor_outputs + 1) / 2
        
        # Clip to thrust limits
        motor_outputs = np.clip(motor_outputs, self.min_thrust, self.max_thrust)
        
        # Scale to PWM
        pwm_outputs = self.min_pwm + motor_outputs * (self.max_pwm - self.min_pwm)
        
        return pwm_outputs
    
    def mix_to_motor_speed(self, thrust: float, roll: float, 
                          pitch: float, yaw: float) -> np.ndarray:
        """
        Convert to motor speed (RPM) instead of PWM.
        
        Returns:
            Motor speeds (RPM array)
        """
        pwm = self.mix(thrust, roll, pitch, yaw)
        
        # Approximate: PWM 1000-2000 -> RPM 0-10000
        rpm = (pwm - 1000) / 1000 * 10000
        
        return rpm
    
    def demix(self, motor_pwm: np.ndarray) -> Tuple[float, float, float, float]:
        """
        Convert motor outputs back to control inputs.
        
        Args:
            motor_pwm: Motor PWM values
            
        Returns:
            (thrust, roll, pitch, yaw)
        """
        # Convert PWM to 0-1
        motor_outputs = (motor_pwm - self.min_pwm) / (self.max_pwm - self.min_pwm)
        
        # Denormalize
        motor_outputs = motor_outputs * 2 - 1
        
        # Inverse mix
        u = np.linalg.lstsq(self.motor_config, motor_outputs, rcond=None)[0]
        
        return u[0], u[1], u[2], u[3]
    
    def get_motor_speeds(self, pwm: np.ndarray) -> np.ndarray:
        """Get motor speeds from PWM."""
        return (pwm - 1000) / 1000 * 10000
    
    def apply_yaw_offset(self, pwm: np.ndarray, yaw_offset: float) -> np.ndarray:
        """
        Apply yaw offset to motors for coordinated turn.
        
        Args:
            yaw_offset: Yaw offset (-1 to 1)
            
        Returns:
            Modified PWM
        """
        offset = yaw_offset * 100  # Max 100us offset
        return pwm + self.prop_dir * offset
    
    def distribute_thrust(self, total_thrust: float, 
                         distribution: np.ndarray = None) -> np.ndarray:
        """
        Distribute thrust across motors.
        
        Args:
            total_thrust: Total thrust needed
            distribution: Weight for each motor (None = equal)
        """
        if distribution is None:
            distribution = np.ones(self.n_motors) / self.n_motors
        
        distribution = distribution / np.sum(distribution)
        
        motor_thrusts = total_thrust * distribution
        
        # Convert to PWM
        pwm = self.min_pwm + motor_thrusts * (self.max_pwm - self.min_pwm)
        
        return pwm
    
    def set_frame_type(self, frame_type: str):
        """Change frame type."""
        if frame_type in self.FRAME_TYPES:
            self.frame_type = frame_type
            config = self.FRAME_TYPES[frame_type]
            self.n_motors = config['motors']
            self.motor_config = np.array(config['config'])
            self.prop_dir = np.array(config['prop_dir'])
    
    def get_motor_config(self) -> dict:
        """Get mixer configuration."""
        return {
            'frame_type': self.frame_type,
            'n_motors': self.n_motors,
            'min_pwm': self.min_pwm,
            'max_pwm': self.max_pwm,
            'motor_config': self.motor_config.tolist()
        }