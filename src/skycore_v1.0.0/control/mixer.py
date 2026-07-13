"""Motor Mixer for quadrotor, hexarotor, and octocopter.

Converts desired thrust and torque to motor PWM commands.

Quadrotor X configuration:
  mixer = [[ 1,  1, -1,  1],    # motor 1
           [ 1, -1, -1, -1],    # motor 2
           [ 1,  1,  1, -1],    # motor 3
           [ 1, -1,  1,  1]]    # motor 4
  # [thrust, roll, pitch, yaw] -> [m1, m2, m3, m4]

Motor to PWM:
  PWM = PWM_min + (PWM_max - PWM_min) * sqrt(F / F_max)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
from numpy.typing import NDArray


@dataclass
class MotorConfig:
    """Motor configuration."""
    n_motors: int = 4
    frame_type: str = "quad_x"  # "quad_plus", "quad_x", "hex", "octo"
    pwm_min: float = 1000
    pwm_max: float = 2000
    motor_time_constant: float = 0.02  # seconds


class MotorMixer:
    """Motor allocation and mixing."""
    
    # Standard mixer matrices
    MIXERS = {
        "quad_plus": np.array([
            [ 1,  0,  1, -1],  # front (CW)
            [ 0,  1, -1, -1],  # right (CCW)
            [-1,  0, -1, -1],  # back (CW)
            [ 0, -1,  1, -1],  # left (CCW)
        ]),
        "quad_x": np.array([
            [ 1,  1, -1,  1],  # front-left (CW)
            [ 1, -1, -1, -1],  # front-right (CCW)
            [ 1,  1,  1, -1],  # back-right (CW)
            [ 1, -1,  1,  1],  # back-left (CCW)
        ]),
        "hex": np.array([
            [ 1,  0.866,  0.5,  1],  # M1
            [ 1,  0.866, -0.5, -1],  # M2
            [ 1,  0,      1,   -1],  # M3
            [ 1,  0,     -1,    1],  # M4
            [ 1, -0.866,  0.5, -1],  # M5
            [ 1, -0.866, -0.5,  1],  # M6
        ]),
        "octo": np.array([
            [ 1,  1,    0.707,  1],  # M1
            [ 1,  0.707, -1,    -1],  # M2
            [ 1,  0,     -0.707, 1],  # M3
            [ 1, -0.707, -1,     1],  # M4
            [ 1, -1,     -0.707, -1],  # M5
            [ 1, -0.707,  1,      1],  # M6
            [ 1,  0,      0.707, -1],  # M7
            [ 1,  0.707,  1,     -1],  # M8
        ]),
    }
    
    def __init__(self, config: Optional[MotorConfig] = None):
        self.config = config or MotorConfig()
        
        self.mixer = self.MIXERS.get(self.config.frame_type, self.MIXERS["quad_x"])
        self.n = self.mixer.shape[1]  # Number of motors
        
        # Motor state
        self.motor_outputs = np.zeros(self.n)
        self.motor_saturations = np.zeros(self.n, dtype=bool)
    
    def mix(
        self,
        thrust: float,
        torque: Tuple[float, float, float]  # (roll, pitch, yaw)
    ) -> NDArray:
        """Convert thrust/torque to motor outputs.
        
        Args:
            thrust: Total thrust (N)
            torque: (roll_torque, pitch_torque, yaw_torque) in N*m
            
        Returns:
            motor_outputs: Motor force commands (n,)
        """
        roll, pitch, yaw = torque
        
        # Combined command: [thrust, roll, pitch, yaw]
        cmd = np.array([thrust, roll, pitch, yaw])
        
        # Motor forces
        forces = self.mixer @ cmd
        
        return forces
    
    def forces_to_pwm(self, forces: NDArray, mass: float = 0.5) -> NDArray:
        """Convert forces to PWM values.
        
        Uses square-root mapping for linear thrust response:
          PWM = PWM_min + (PWM_max - PWM_min) * sqrt(F / F_max)
        
        Args:
            forces: Motor forces (n,)
            mass: Quadrotor mass (kg)
            
        Returns:
            pwm: Motor PWM values (n,)
        """
        # Max force per motor (at max PWM)
        # Assuming total max thrust = 2 * mg for agile flight
        F_max = 2 * 9.81 * mass / self.n
        
        pwm = np.zeros_like(forces)
        
        for i, F in enumerate(forces):
            if F >= 0:
                # Positive force: map to PWM
                ratio = np.clip(F / F_max, 0, 1)
                pwm[i] = self.config.pwm_min + (self.config.pwm_max - self.config.pwm_min) * np.sqrt(ratio)
            else:
                # Negative force: can't reverse, set to minimum
                pwm[i] = self.config.pwm_min
        
        return pwm
    
    def pwm_to_forces(self, pwm: NDArray, mass: float = 0.5) -> NDArray:
        """Convert PWM to forces (inverse mapping).
        
        Args:
            pwm: Motor PWM values (n,)
            mass: Quadrotor mass
            
        Returns:
            forces: Motor forces (n,)
        """
        F_max = 2 * 9.81 * mass / self.n
        
        forces = np.zeros_like(pwm)
        for i, p in enumerate(pwm):
            ratio = (p - self.config.pwm_min) / (self.config.pwm_max - self.config.pwm_min)
            ratio = np.clip(ratio, 0, 1)
            forces[i] = ratio ** 2 * F_max
        
        return forces
    
    def saturate(self, forces: NDArray, F_max: Optional[float] = None) -> Tuple[NDArray, float]:
        """Handle motor saturation by scaling.
        
        Args:
            forces: Motor forces (n,)
            F_max: Maximum per-motor force
            
        Returns:
            (forces_scaled, scale_factor)
        """
        if F_max is None:
            F_max = 10.0  # Default max force
        
        # Check for saturation
        max_force = np.max(np.abs(forces))
        scale = 1.0
        
        if max_force > F_max:
            scale = F_max / max_force
            forces = forces * scale
        
        # Track saturation
        self.motor_saturations = np.abs(forces) >= F_max * 0.99
        
        return forces, scale
    
    def handle_motor_failure(
        self,
        failed_motors: list[int],
        thrust: float,
        torque: Tuple[float, float, float]
    ) -> Tuple[NDArray, bool]:
        """Handle motor failure by redistributing control.
        
        Args:
            failed_motors: List of failed motor indices
            thrust: Desired thrust
            torque: Desired torque
            
        Returns:
            (forces, controllable): Motor forces and whether still controllable
        """
        if len(failed_motors) >= self.n - 1:
            return np.zeros(self.n), False
        
        # Create reduced mixer (excluding failed motors)
        active_mask = np.ones(self.n, dtype=bool)
        for i in failed_motors:
            active_mask[i] = False
        
        # For simplicity, scale remaining motors
        forces = self.mix(thrust, torque)
        n_active = np.sum(active_mask)
        
        # Scale up active motors to compensate
        scale = self.n / n_active
        forces = forces * scale
        
        # Zero out failed motors
        for i in failed_motors:
            forces[i] = 0
        
        return forces, True
    
    def compute_control_allocation(
        self,
        thrust: float,
        torque: Tuple[float, float, float]
    ) -> Tuple[NDArray, NDArray, float]:
        """Full control allocation: mix + saturate + convert to PWM.
        
        Args:
            thrust: Total thrust (N)
            torque: (roll, pitch, yaw) torque (N*m)
            
        Returns:
            (pwm, forces, scale): PWM commands, forces, and saturation scale
        """
        # Mix
        forces = self.mix(thrust, torque)
        
        # Saturate
        forces, scale = self.saturate(forces)
        
        # Convert to PWM
        pwm = self.forces_to_pwm(forces)
        
        return pwm, forces, scale


def demo_motor_mixer():
    """Demonstrate motor mixer."""
    print("=" * 60)
    print("Motor Mixer Demo")
    print("=" * 60)
    
    config = MotorConfig(frame_type="quad_x")
    mixer = MotorMixer(config)
    
    print(f"\nMixer matrix (quad_x):\n{mixer.mixer}")
    
    # Test various commands
    tests = [
        ("Hover", 9.81 * 0.5, (0, 0, 0)),  # Hover: thrust = mg, no torque
        ("Roll +", 9.81 * 0.5, (1, 0, 0)),  # Roll right
        ("Pitch +", 9.81 * 0.5, (0, 1, 0)),  # Pitch forward
        ("Yaw +", 9.81 * 0.5, (0, 0, 0.5)),  # Yaw CW
        ("Climb", 15, (0, 0, 0)),  # Accelerating climb
    ]
    
    print("\n" + "=" * 40)
    for name, thrust, torque in tests:
        forces = mixer.mix(thrust, torque)
        pwm, forces_sat, scale = mixer.compute_control_allocation(thrust, torque)
        
        print(f"\n{name}: thrust={thrust:.1f}N, torque={torque}")
        print(f"  Forces: {forces}")
        print(f"  PWM: {pwm}")
        print(f"  Saturation scale: {scale:.3f}")


if __name__ == "__main__":
    demo_motor_mixer()