"""Digital Twin physics engine for drone simulation.

Implements:
- Rigid body dynamics
- Aerodynamic forces (drag, lift, thrust)
- Environmental effects (wind, turbulence)
- Sensor simulation
- Physics-based collision detection
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple, List
import numpy as np
from numpy.typing import NDArray
import time


@dataclass
class RigidBody:
    """Rigid body state."""
    position: NDArray        # m (NED)
    velocity: NDArray       # m/s
    attitude: NDArray       # quat [w, x, y, z]
    angular_velocity: NDArray  # rad/s
    
    # Derivatives
    acceleration: NDArray = field(default_factory=lambda: np.zeros(3))
    angular_acceleration: NDArray = field(default_factory=lambda: np.zeros(3))


@dataclass
class DronePhysicsConfig:
    """Drone physics configuration."""
    mass: float = 0.5           # kg
    inertia: NDArray = field(default_factory=lambda: np.diag([0.001, 0.001, 0.002]))  # kg*m²
    
    # Dimensions
    arm_length: float = 0.15    # m
    height: float = 0.05        # m
    
    # Propulsion
    max_thrust: float = 10.0    # N per motor
    motor_time_constant: float = 0.02  # s
    
    # Aerodynamics
    drag_coefficient: float = 0.5
    frontal_area: float = 0.01  # m²
    
    # Environment
    gravity: float = 9.81       # m/s²
    air_density: float = 1.225  # kg/m³
    
    # Wind
    wind_speed: NDArray = field(default_factory=lambda: np.zeros(3))  # m/s
    turbulence_intensity: float = 0.0


@dataclass
class EnvironmentState:
    """Environment state."""
    temperature: float = 20.0   # Celsius
    pressure: float = 101325.0  # Pa
    humidity: float = 0.5       # 0-1
    
    # Wind (NED frame)
    wind: NDArray = field(default_factory=lambda: np.zeros(3))
    wind_direction: float = 0.0  # rad (from North)
    wind_speed: float = 0.0      # m/s
    
    # Turbulence
    turbulence: float = 0.0  # 0-1
    
    def update_wind(self, speed: float, direction: float) -> None:
        """Update wind conditions."""
        self.wind_speed = speed
        self.wind_direction = direction
        self.wind = np.array([
            speed * np.sin(direction),
            speed * np.cos(direction),
            0
        ])


class AerodynamicModel:
    """Aerodynamic force and moment model."""
    
    def __init__(self, config: DronePhysicsConfig):
        self.config = config
    
    def compute_drag(self, velocity: NDArray) -> NDArray:
        """Compute aerodynamic drag.
        
        F_drag = 0.5 * rho * v² * Cd * A * (-v_hat)
        """
        speed = np.linalg.norm(velocity)
        
        if speed < 0.1:
            return np.zeros(3)
        
        v_hat = velocity / speed
        
        drag_magnitude = 0.5 * self.config.air_density * speed ** 2 * \
                         self.config.drag_coefficient * self.config.frontal_area
        
        return -drag_magnitude * v_hat
    
    def compute_lift(self, velocity: NDArray, thrust: float) -> NDArray:
        """Compute lift from propeller wash."""
        # Simplified lift model
        # Lift proportional to thrust and forward speed
        speed = np.linalg.norm(velocity)
        
        if speed < 0.1:
            return np.zeros(3)
        
        # Lift acts perpendicular to velocity (upward component)
        v_horizontal = np.array([velocity[0], velocity[1], 0])
        v_horizontal_norm = np.linalg.norm(v_horizontal)
        
        if v_horizontal_norm > 0.1:
            lift = thrust * 0.1 * (v_horizontal / v_horizontal_norm)
            lift[2] = thrust * 0.9  # Mostly upward
        else:
            lift = np.array([0, 0, thrust])
        
        return lift
    
    def compute_gyroscopic_torque(
        self,
        angular_velocity: NDArray,
        propeller_spin_rates: List[float]
    ) -> NDArray:
        """Compute gyroscopic torque from spinning propellers."""
        # Each propeller produces gyroscopic moment
        # M_gyro = omega_prop x I_prop * omega_prop
        
        total_torque = np.zeros(3)
        
        for omega_prop in propeller_spin_rates:
            # Simplified: treat each propeller as a disk
            # Torque = I_prop * d_omega/dt (in body frame)
            I_prop = 0.0001  # kg*m² (approximate)
            
            # Cross product with angular velocity
            # In practice, need propeller orientation
            pass
        
        return total_torque


class PropellerModel:
    """Propeller thrust and torque model."""
    
    def __init__(self, config: DronePhysicsConfig):
        self.config = config
        
        # Motor model
        self.motor_time_constant = config.motor_time_constant
        self.current_rpm = np.zeros(4)
        self.target_rpm = np.zeros(4)
        
        # Propeller coefficients
        # Thrust = Ct * rho * n² * D⁴
        # Torque = Cq * rho * n² * D⁵
        self.Ct = 1.0e-5    # Thrust coefficient
        self.Cq = 1.5e-7    # Torque coefficient
        self.prop_diameter = 0.1  # m
        
        # Motor limits
        self.max_rpm = 10000
    
    def update_motors(self, pwm: NDArray, dt: float) -> NDArray:
        """Update motor RPM based on PWM commands.
        
        Args:
            pwm: PWM values (4,)
            dt: Time step
            
        Returns:
            rpm: Current RPM (4,)
        """
        # PWM to RPM (simplified linear model)
        self.target_rpm = (pwm - 1000) / 1000 * self.max_rpm
        
        # First-order dynamics
        alpha = 1.0 / self.motor_time_constant
        self.current_rpm += (self.target_rpm - self.current_rpm) * alpha * dt
        
        return self.current_rpm.copy()
    
    def compute_thrust_and_torque(
        self,
        rpm: NDArray
    ) -> Tuple[float, NDArray]:
        """Compute total thrust and torque from propeller RPM.
        
        Args:
            rpm: Propeller RPM (4,)
            
        Returns:
            (total_thrust, torque_body)
        """
        # Thrust per propeller
        # F = Ct * rho * n² * D⁴ (n in rev/s)
        n = rpm / 60  # rev/s
        rho = self.config.air_density
        D = self.prop_diameter
        
        thrusts = self.Ct * rho * n ** 2 * D ** 4
        
        # Quadrotor configuration (X-frame)
        # Motor layout (view from above):
        #   M1 (+)
        # M4    M2
        #   M3 (-)
        
        # Thrust acts in body z direction (downward for positive thrust)
        total_thrust = np.sum(thrustes)
        
        # Torque from each motor
        # Counter-rotating props for yaw authority
        # M1 CW, M2 CCW, M3 CW, M4 CCW
        
        torques = np.zeros(3)
        
        for i, (F, omega) in enumerate(zip(thrustes, rpm)):
            # Propeller torque (reaction torque)
            # CW rotation gives negative yaw moment
            direction = 1 if i in [0, 2] else -1  # CW vs CCW
            
            torque_z = direction * self.Cq * rho * (rpm[i] / 60) ** 2 * D ** 5
            
            # Moment from arm
            arm_x = self.config.arm_length * 0.707  # X-frame diagonal
            arm_y = self.config.arm_length * 0.707
            
            # Force produces moment about CG
            torques[0] += arm_y * F  # Roll
            torques[1] -= arm_x * F  # Pitch
            torques[2] += torque_z   # Yaw
        
        return total_thrust, torques


class PhysicsWorld:
    """Physics simulation world."""
    
    def __init__(self, config: Optional[DronePhysicsConfig] = None):
        self.config = config or DronePhysicsConfig()
        
        self.drone = RigidBody(
            position=np.array([0, 0, -10]),
            velocity=np.zeros(3),
            attitude=np.array([1, 0, 0, 0]),  # Identity quaternion
            angular_velocity=np.zeros(3)
        )
        
        self.propeller = PropellerModel(self.config)
        self.aerodynamics = AerodynamicModel(self.config)
        self.environment = EnvironmentState()
        
        self.time = 0.0
    
    def step(self, pwm: NDArray, dt: float) -> RigidBody:
        """Step physics simulation.
        
        Args:
            pwm: Motor PWM values (4,)
            dt: Time step
            
        Returns:
            Updated rigid body state
        """
        self.time += dt
        
        # Update motors
        rpm = self.propeller.update_motors(pwm, dt)
        
        # Compute forces
        thrust, torque_body = self.propeller.compute_thrust_and_torque(rpm)
        
        # Rotation matrix from body to world
        R = self._quaternion_to_rotation(self.drone.attitude)
        R_body = R.T  # World to body
        
        # Gravity in body frame
        gravity_body = R_body @ np.array([0, 0, self.config.gravity])
        
        # Thrust in body frame (z-down)
        thrust_body = np.array([0, 0, thrust])
        
        # Aerodynamic drag (in world frame)
        air_velocity = self.drone.velocity - self.environment.wind
        drag = self.aerodynamics.compute_drag(air_velocity)
        drag_body = R_body @ drag
        
        # Total force in body frame
        F_body = gravity_body + thrust_body + drag_body
        
        # Linear acceleration (F = ma)
        acceleration = F_body / self.config.mass
        
        # Torque in body frame
        torque_total = torque_body.copy()
        
        # Gyroscopic effects
        # gyroscopic = self.aerodynamics.compute_gyroscopic_torque(
        #     self.drone.angular_velocity, rpm
        # )
        # torque_total += gyroscopic
        
        # Angular acceleration (M = I * alpha)
        alpha = np.linalg.inv(self.config.inertia) @ torque_total
        
        # Integrate velocity
        self.drone.velocity += acceleration * dt
        
        # Integrate position
        self.drone.position += self.drone.velocity * dt
        
        # Integrate angular velocity
        self.drone.angular_velocity += alpha * dt
        
        # Integrate attitude (quaternion)
        omega = self.drone.angular_velocity
        q = self.drone.attitude
        
        # Quaternion derivative
        omega_quat = np.array([0, omega[0], omega[1], omega[2]])
        q_dot = 0.5 * self._quaternion_multiply(q, omega_quat)
        
        self.drone.attitude += q_dot * dt
        
        # Normalize quaternion
        self.drone.attitude /= np.linalg.norm(self.drone.attitude)
        
        # Store accelerations
        self.drone.acceleration = acceleration
        self.drone.angular_acceleration = alpha
        
        # Ground collision
        if self.drone.position[2] > 0:  # Above ground
            self.drone.position[2] = 0
            self.drone.velocity[2] = 0
        
        return self.drone
    
    @staticmethod
    def _quaternion_to_rotation(q: NDArray) -> NDArray:
        """Convert quaternion to rotation matrix."""
        w, x, y, z = q
        
        return np.array([
            [1 - 2*(y**2 + z**2), 2*(x*y - w*z), 2*(x*z + w*y)],
            [2*(x*y + w*z), 1 - 2*(x**2 + z**2), 2*(y*z - w*x)],
            [2*(x*z - w*y), 2*(y*z + w*x), 1 - 2*(x**2 + y**2)]
        ])
    
    @staticmethod
    def _quaternion_multiply(q1: NDArray, q2: NDArray) -> NDArray:
        """Multiply two quaternions."""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ])


class SensorSimulator:
    """Simulate onboard sensors."""
    
    def __init__(self, physics: PhysicsWorld):
        self.physics = physics
        
        # Noise parameters
        self.gps_noise_std = 0.5       # m
        self.gyro_noise_std = 0.01      # rad/s
        self.accel_noise_std = 0.1      # m/s²
        self.baro_noise_std = 0.5       # m
        self.mag_noise_std = 0.05       # rad
    
    def simulate_gps(self, true_position: NDArray) -> Tuple[NDArray, float]:
        """Simulate GPS reading with noise and dropout."""
        # Add noise
        noise = np.random.randn(3) * self.gps_noise_std
        position = true_position + noise
        
        # Simulate HDOP
        hdop = 1.0 + np.random.rand() * 0.5
        
        return position, hdop
    
    def simulate_imu(
        self,
        true_acceleration: NDArray,
        true_angular_velocity: NDArray
    ) -> Tuple[NDArray, NDArray]:
        """Simulate IMU (accelerometer + gyroscope)."""
        accel = true_acceleration + np.random.randn(3) * self.accel_noise_std
        gyro = true_angular_velocity + np.random.randn(3) * self.gyro_noise_std
        
        return accel, gyro
    
    def simulate_barometer(self, true_altitude: float) -> float:
        """Simulate barometric altitude."""
        noise = np.random.randn() * self.baro_noise_std
        return true_altitude + noise
    
    def simulate_magnetometer(self, heading: float) -> float:
        """Simulate magnetometer heading."""
        noise = np.random.randn() * self.mag_noise_std
        return heading + noise


class DigitalTwin:
    """Digital twin combining physics and sensors."""
    
    def __init__(self, config: Optional[DronePhysicsConfig] = None):
        self.physics = PhysicsWorld(config)
        self.sensors = SensorSimulator(self.physics)
        
        self.recording = []
        self.max_recording_length = 10000
    
    def step(self, pwm: NDArray, dt: float) -> dict:
        """Step digital twin simulation.
        
        Returns:
            Sensor data dictionary
        """
        # Step physics
        state = self.physics.step(pwm, dt)
        
        # Simulate sensors
        gps_pos, gps_hdop = self.sensors.simulate_gps(state.position)
        
        accel, gyro = self.sensors.simulate_imu(
            state.acceleration,
            state.angular_velocity
        )
        
        baro_alt = self.sensors.simulate_barometer(-state.position[2])  # Above ground
        
        # Compute heading from velocity or quaternion
        if np.linalg.norm(state.velocity[:2]) > 0.1:
            heading = np.arctan2(state.velocity[0], state.velocity[1])
        else:
            R = self.physics._quaternion_to_rotation(state.attitude)
            heading = np.arctan2(-R[0, 1], R[0, 0])
        
        mag_heading = self.sensors.simulate_magnetometer(heading)
        
        # Record
        sensor_data = {
            'time': self.physics.time,
            'position': state.position.copy(),
            'velocity': state.velocity.copy(),
            'attitude': state.attitude.copy(),
            'gps': {'position': gps_pos, 'hdop': gps_hdop},
            'accel': accel,
            'gyro': gyro,
            'baro_altitude': baro_alt,
            'heading': mag_heading
        }
        
        self.recording.append(sensor_data)
        
        # Trim recording
        if len(self.recording) > self.max_recording_length:
            self.recording = self.recording[-self.max_recording_length:]
        
        return sensor_data
    
    def replay(self, start_time: float, duration: float) -> List[dict]:
        """Replay recorded data."""
        end_time = start_time + duration
        
        return [
            s for s in self.recording
            if start_time <= s['time'] <= end_time
        ]


def demo_physics():
    """Demonstrate physics simulation."""
    print("=" * 60)
    print("Digital Twin Physics Demo")
    print("=" * 60)
    
    # Create physics world
    config = DronePhysicsConfig()
    physics = PhysicsWorld(config)
    
    print("\nSimulating hover...")
    
    dt = 0.01
    times = []
    positions = []
    altitudes = []
    
    # Hover: PWM ~1500 (neutral)
    pwm_hover = np.array([1500, 1500, 1500, 1500])
    
    for i in range(1000):
        state = physics.step(pwm_hover, dt)
        
        if i % 50 == 0:
            print(f"  t={physics.time:.2f}s: pos=({state.position[0]:.2f}, {state.position[1]:.2f}, {state.position[2]:.2f})")
        
        times.append(physics.time)
        positions.append(state.position.copy())
        altitudes.append(-state.position[2])
    
    print(f"\nFinal altitude: {-state.position[2]:.2f}m")
    
    # Digital twin
    print("\n" + "=" * 40)
    print("Digital Twin with sensors")
    print("=" * 40)
    
    twin = DigitalTwin(config)
    
    # Step with simulated data
    for _ in range(100):
        sensor_data = twin.step(pwm_hover, dt)
        
        if _ % 20 == 0:
            print(f"  GPS: ({sensor_data['gps']['position'][0]:.2f}, "
                  f"{sensor_data['gps']['position'][1]:.2f}, "
                  f"{sensor_data['gps']['position'][2]:.2f})")
            print(f"  IMU accel: ({sensor_data['accel'][0]:.3f}, "
                  f"{sensor_data['accel'][1]:.3f}, "
                  f"{sensor_data['accel'][2]:.3f})")
            print(f"  Baro altitude: {sensor_data['baro_altitude']:.2f}m")
    
    print(f"\nRecorded {len(twin.recording)} samples")


if __name__ == "__main__":
    demo_physics()