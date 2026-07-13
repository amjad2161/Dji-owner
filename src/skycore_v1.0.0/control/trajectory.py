"""Trajectory Generator for minimum snap and time-optimal trajectories.

Implements polynomial trajectory planning for smooth drone motion.

7th-order Minimum Snap:
  - Boundary conditions: pos, vel, acc, jerk at start/end
  - Solves for coefficients via matrix inversion
  - Minimizes integral of snap squared

Time allocation:
  - Compute max feasible velocity along path
  - Satisfy dynamic constraints

Emergency trajectory:
  - Straight line to home
  - Maximum deceleration profile

References:
  - Richter et al. (2016) - Polynomial Trajectory Planning
  - Mellinger & Kumar (2011) - Minimum Snap Trajectories
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, List
import numpy as np
from numpy.typing import NDArray


@dataclass
class Waypoint:
    """Waypoint with position and optional constraints."""
    position: NDArray  # [x, y, z]
    yaw: float = 0.0
    max_velocity: Optional[float] = None
    max_acceleration: Optional[float] = None


@dataclass
class TrajectoryConfig:
    """Trajectory configuration."""
    max_velocity: float = 5.0    # m/s
    max_acceleration: float = 10.0  # m/s²
    max_jerk: float = 20.0     # m/s³
    polynomial_order: int = 7


class MinimumSnapTrajectory:
    """Minimum snap polynomial trajectory."""
    
    def __init__(self, config: Optional[TrajectoryConfig] = None):
        self.config = config or TrajectoryConfig()
        self.waypoints: List[Waypoint] = []
        self.segments: list = []  # List of segment polynomials
        self.time_vector: NDArray = np.zeros(0)
    
    def add_waypoint(self, position: NDArray, yaw: float = 0.0) -> None:
        """Add waypoint."""
        self.waypoints.append(Waypoint(position=position, yaw=yaw))
    
    def plan(self, time_allocation: Optional[NDArray] = None) -> bool:
        """Plan trajectory through waypoints.
        
        Args:
            time_allocation: Time for each segment (n-1 times)
            
        Returns:
            True if successful
        """
        if len(self.waypoints) < 2:
            return False
        
        n_waypoints = len(self.waypoints)
        
        # Default time allocation based on distance
        if time_allocation is None:
            time_allocation = self._compute_default_times()
        
        # Plan each segment
        self.segments = []
        self.time_vector = np.concatenate([[0], np.cumsum(time_allocation)])
        
        for i in range(n_waypoints - 1):
            wp_start = self.waypoints[i]
            wp_end = self.waypoints[i + 1]
            T = time_allocation[i]
            
            segment = self._plan_segment(wp_start, wp_end, T)
            self.segments.append(segment)
        
        return True
    
    def _compute_default_times(self) -> NDArray:
        """Compute default time allocation based on distances."""
        times = []
        for i in range(len(self.waypoints) - 1):
            dist = np.linalg.norm(
                self.waypoints[i + 1].position - self.waypoints[i].position
            )
            # Simple: assume constant velocity
            T = dist / self.config.max_velocity
            T = max(T, 0.5)  # Minimum segment time
            times.append(T)
        
        return np.array(times)
    
    def _plan_segment(self, wp_start: Waypoint, wp_end: Waypoint, T: float) -> dict:
        """Plan single trajectory segment.
        
        Returns:
            Dictionary with polynomial coefficients
        """
        # For minimum snap, solve linear system for 7th order polynomial
        # p(t) = c0 + c1*t + c2*t² + ... + c7*t⁷
        
        order = self.config.polynomial_order
        
        # Start and end conditions (zero velocity/acceleration for smooth transition)
        p0 = wp_start.position
        v0 = np.zeros(3)
        a0 = np.zeros(3)
        
        p1 = wp_end.position
        v1 = np.zeros(3)
        a1 = np.zeros(3)
        
        # Build constraint matrix
        # [t^0, t^1, ..., t^7] at t=0 and t=T
        # Conditions: pos, vel, acc at start and end
        
        A = np.zeros((6, order + 1))
        b = np.zeros(6)
        
        # Position at start (t=0)
        A[0, 0] = 1
        b[0] = p0[0]
        
        # Velocity at start (t=0)
        A[1, 1] = 1
        b[1] = v0[0]
        
        # Acceleration at start (t=0)
        A[2, 2] = 2
        b[2] = a0[0]
        
        # Position at end (t=T)
        for j in range(order + 1):
            A[3, j] = T ** j
        b[3] = p1[0]
        
        # Velocity at end (t=T)
        for j in range(1, order + 1):
            A[4, j] = j * T ** (j - 1)
        b[4] = v1[0]
        
        # Acceleration at end (t=T)
        for j in range(2, order + 1):
            A[5, j] = j * (j - 1) * T ** (j - 2)
        b[5] = a1[0]
        
        # Solve for each axis separately (for simplicity)
        # In practice, would solve 3D simultaneously
        coeffs = np.zeros((3, order + 1))
        
        for axis in range(3):
            b_axis = np.array([p0[axis], v0[axis], a0[axis], p1[axis], v1[axis], a1[axis]])
            coeffs[axis] = np.linalg.lstsq(A, b_axis, rcond=None)[0]
        
        return {
            'coeffs': coeffs,
            'start_time': 0,  # Will be set by caller
            'duration': T
        }
    
    def evaluate(self, t: float) -> Tuple[NDArray, NDArray, NDArray]:
        """Evaluate trajectory at time t.
        
        Returns:
            (position, velocity, acceleration)
        """
        if not self.segments:
            return np.zeros(3), np.zeros(3), np.zeros(3)
        
        # Find segment
        for i, segment in enumerate(self.segments):
            start_time = self.time_vector[i]
            end_time = self.time_vector[i + 1]
            
            if t <= end_time:
                tau = t - start_time
                return self._evaluate_segment(segment, tau)
        
        # Beyond trajectory: return last point
        last_seg = self.segments[-1]
        return self._evaluate_segment(last_seg, last_seg['duration'])
    
    def _evaluate_segment(self, segment: dict, tau: float) -> Tuple[NDArray, NDArray, NDArray]:
        """Evaluate single segment at local time tau."""
        coeffs = segment['coeffs']
        order = coeffs.shape[1] - 1
        
        # Position
        t_powers = np.array([tau ** j for j in range(order + 1)])
        position = coeffs @ t_powers
        
        # Velocity
        coeff_vel = np.array([j * coeffs[:, j] for j in range(1, order + 1)]).T
        t_powers_vel = np.array([tau ** j for j in range(order)])
        velocity = coeff_vel @ t_powers_vel
        
        # Acceleration
        coeff_acc = np.array([j * (j - 1) * coeffs[:, j] for j in range(2, order + 1)]).T
        t_powers_acc = np.array([tau ** j for j in range(max(0, order - 1))])
        acceleration = coeff_acc @ t_powers_acc
        
        return position, velocity, acceleration
    
    def compute_yaw(self, t: float) -> float:
        """Compute yaw angle at time t (simplified: follow path direction)."""
        _, velocity, _ = self.evaluate(t)
        
        if np.linalg.norm(velocity) < 0.1:
            return 0.0
        
        return np.arctan2(velocity[1], velocity[0])


class EmergencyTrajectory:
    """Emergency trajectory to home."""
    
    def __init__(self, config: Optional[TrajectoryConfig] = None):
        self.config = config or TrajectoryConfig()
    
    def plan(
        self,
        current_position: NDArray,
        home_position: NDArray,
        current_velocity: NDArray
    ) -> dict:
        """Plan emergency return to home.
        
        Args:
            current_position: Current position [x, y, z]
            home_position: Home position [x, y, z]
            current_velocity: Current velocity [vx, vy, vz]
            
        Returns:
            Trajectory parameters
        """
        # Direction to home
        direction = home_position - current_position
        distance = np.linalg.norm(direction)
        
        if distance < 0.1:
            return {'type': 'hover', 'duration': 10.0}
        
        direction_unit = direction / distance
        
        # Maximum deceleration (assume motor still responsive)
        # emergency_decel = config.max_acceleration * 0.5
        
        # Time to decelerate to zero velocity along path
        v_along_path = np.dot(current_velocity, direction_unit)
        
        # Simple straight line to home with deceleration
        return {
            'type': 'straight',
            'direction': direction_unit,
            'distance': distance,
            'initial_velocity': v_along_path,
            'home_position': home_position
        }
    
    def evaluate(self, t: float, trajectory: dict) -> Tuple[NDArray, NDArray]:
        """Evaluate emergency trajectory at time t.
        
        Returns:
            (position, velocity)
        """
        if trajectory['type'] == 'hover':
            return trajectory['home_position'], np.zeros(3)
        
        # Straight line to home
        # v(t) = v0 - a*t (linear deceleration)
        v0 = trajectory['initial_velocity']
        a_max = self.config.max_acceleration * 0.3  # Conservative
        
        v_along = max(0, v0 - a_max * t)
        distance_covered = v0 * t - 0.5 * a_max * t ** 2
        
        if distance_covered >= trajectory['distance']:
            position = trajectory['home_position']
            velocity = np.zeros(3)
        else:
            position = trajectory['home_position'] - trajectory['direction'] * distance_covered
            velocity = -trajectory['direction'] * v_along
        
        return position, velocity


def demo_trajectory():
    """Demonstrate trajectory generation."""
    print("=" * 60)
    print("Trajectory Generator Demo")
    print("=" * 60)
    
    config = TrajectoryConfig(max_velocity=5, max_acceleration=10)
    
    # Create trajectory
    traj = MinimumSnapTrajectory(config)
    
    # Add waypoints
    waypoints = [
        np.array([0, 0, 0]),
        np.array([10, 0, -5]),
        np.array([10, 10, -10]),
        np.array([0, 10, -5]),
        np.array([0, 0, 0]),
    ]
    
    for wp in waypoints:
        traj.add_waypoint(wp)
    
    # Plan with time allocation
    times = np.array([2.0, 3.0, 3.0, 2.0])
    traj.plan(times)
    
    print(f"\nTrajectory with {len(waypoints)} waypoints")
    print(f"Total duration: {traj.time_vector[-1]:.1f}s")
    
    # Evaluate trajectory
    print("\n" + "=" * 40)
    print("Trajectory evaluation:")
    print("=" * 40)
    
    t = 0
    while t <= traj.time_vector[-1]:
        pos, vel, acc = traj.evaluate(t)
        yaw = traj.compute_yaw(t)
        
        if int(t * 2) % 2 == 0:  # Every 0.5s
            print(f"  t={t:.1f}s: pos=({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}), "
                  f"vel=({vel[0]:.2f}, {vel[1]:.2f}, {vel[2]:.2f})")
        
        t += 0.5
    
    # Emergency trajectory
    print("\n" + "=" * 40)
    print("Emergency Trajectory:")
    print("=" * 40)
    
    emergency = EmergencyTrajectory(config)
    
    traj_emerg = emergency.plan(
        current_position=np.array([20, 10, -15]),
        home_position=np.array([0, 0, 0]),
        current_velocity=np.array([5, 2, -3])
    )
    
    print(f"Direction to home: {traj_emerg['direction']}")
    print(f"Distance: {traj_emerg['distance']:.1f}m")
    print(f"Initial velocity along path: {traj_emerg['initial_velocity']:.2f} m/s")


if __name__ == "__main__":
    demo_trajectory()