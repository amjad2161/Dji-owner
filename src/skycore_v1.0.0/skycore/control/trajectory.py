"""
SkyCore Trajectory Generator
===========================
Trajectory planning and generation for drone missions.
"""

import numpy as np
from typing import Tuple, List, Optional, Callable
import logging

log = logging.getLogger(__name__)


class TrajectoryGenerator:
    """
    Trajectory generator for smooth drone movements.
    
    Supports:
    - Minimum snap trajectories
    - Polynomial trajectories
    - Circular/helical paths
    - Emergency trajectories
    """
    
    def __init__(self, max_velocity: float = 15.0, max_acceleration: float = 10.0):
        """
        Initialize trajectory generator.
        
        Args:
            max_velocity: Maximum velocity (m/s)
            max_acceleration: Maximum acceleration (m/s^2)
        """
        self.v_max = max_velocity
        self.a_max = max_acceleration
        
        self.dt = 0.01  # Time step
    
    def minimum_jerk(self, p0: np.ndarray, p1: np.ndarray, 
                    v0: np.ndarray, v1: np.ndarray,
                    a0: np.ndarray, a1: np.ndarray,
                    T: float) -> Callable:
        """
        Generate minimum jerk trajectory.
        
        Args:
            p0, p1: Start and end positions
            v0, v1: Start and end velocities
            a0, a1: Start and end accelerations
            T: Duration
            
        Returns:
            Trajectory function f(t) -> position
        """
        def trajectory(t: float) -> np.ndarray:
            if t < 0:
                return p0
            if t > T:
                return p1
            
            # Minimum jerk coefficients
            T2 = T * T
            T3 = T2 * T
            T4 = T3 * T
            T5 = T4 * T
            
            # Compute coefficients
            a = (-2*T5*v0 + 3*T4*v1 + 6*T3*a0 + 6*T3*a1 + 12*T2*(p0 - p1)) / (-T5)
            b = (-3*T4*v0 - T4*v1 + T3*a0 - 2*T3*a1 + 18*T*(p1 - p0)) / (-T5)
            c = (-6*T3*v0 - 3*T3*v1 + 6*T2*a0 + 6*T2*a1 + 36*T*(p0 - p1)) / (-T5)
            d = (-4*T2*v0 - T2*v1 + T*a0 - T*a1 + 24*(p1 - p0)) / (-T5)
            e = (-6*T*v0 - 2*T*v1 + 2*a0 + 2*a1 + 24*(p0 - p1)) / (-T5)
            f = (-2*v0 - v1 + a1 - a0 + 12*(p1 - p0)) / (-T5)
            
            # Evaluate polynomial
            pos = p0 + v0*t + 0.5*a0*t**2 + (1/6)*b*t**3 + (1/12)*c*t**4 + (1/20)*d*t**5 + (1/30)*e*t**6 + (1/42)*f*t**7
            
            return pos
        
        return trajectory
    
    def minimum_snap(self, waypoints: List[np.ndarray], 
                    max_velocity: Optional[float] = None,
                    max_acceleration: Optional[float] = None) -> List[Callable]:
        """
        Generate minimum snap trajectory through waypoints.
        
        Returns:
            List of trajectory functions, one per segment
        """
        if max_velocity is None:
            max_velocity = self.v_max
        if max_acceleration is None:
            max_acceleration = self.a_max
        
        n = len(waypoints)
        if n < 2:
            return []
        
        # Compute segment times based on distances
        times = [0]
        for i in range(n - 1):
            dist = np.linalg.norm(waypoints[i+1] - waypoints[i])
            
            # Time based on velocity and acceleration constraints
            t_accel = max_velocity / max_acceleration
            d_accel = 0.5 * max_velocity * t_accel
            
            if dist < 2 * d_accel:
                t_seg = 2 * np.sqrt(dist / max_acceleration)
            else:
                t_seg = dist / max_velocity + t_accel
            
            times.append(times[-1] + t_seg)
        
        trajectories = []
        for i in range(n - 1):
            p0 = waypoints[i]
            p1 = waypoints[i+1]
            T = times[i+1] - times[i]
            
            traj = self.minimum_jerk(p0, p1, np.zeros(3), np.zeros(3),
                                    np.zeros(3), np.zeros(3), T)
            trajectories.append(traj)
        
        return trajectories
    
    def circular_trajectory(self, center: np.ndarray, radius: float,
                          altitude: float, angular_velocity: float,
                          direction: int = 1) -> Callable:
        """
        Generate circular trajectory.
        
        Args:
            center: Circle center (x, y)
            radius: Circle radius
            altitude: Flight altitude
            angular_velocity: Angular velocity (rad/s)
            direction: 1 = CCW, -1 = CW
            
        Returns:
            Trajectory function f(t) -> (x, y, z)
        """
        def trajectory(t: float) -> np.ndarray:
            theta = direction * angular_velocity * t
            
            x = center[0] + radius * np.cos(theta)
            y = center[1] + radius * np.sin(theta)
            z = altitude
            
            return np.array([x, y, z])
        
        return trajectory
    
    def helical_trajectory(self, center: np.ndarray, radius: float,
                         start_alt: float, end_alt: float,
                         angular_velocity: float, direction: int = 1,
                         num_turns: int = 1) -> Callable:
        """
        Generate helical trajectory.
        
        Args:
            center: Helix axis center
            radius: Helix radius
            start_alt, end_alt: Start and end altitudes
            angular_velocity: Angular velocity
            direction: Rotation direction
            num_turns: Number of turns
            
        Returns:
            Trajectory function
        """
        total_time = num_turns * 2 * np.pi / angular_velocity
        
        def trajectory(t: float) -> np.ndarray:
            if t > total_time:
                t = total_time
            
            theta = direction * angular_velocity * t
            progress = t / total_time
            
            x = center[0] + radius * np.cos(theta)
            y = center[1] + radius * np.sin(theta)
            z = start_alt + (end_alt - start_alt) * progress
            
            return np.array([x, y, z])
        
        return trajectory
    
    def line_trajectory(self, start: np.ndarray, end: np.ndarray,
                       velocity: float) -> Callable:
        """
        Generate straight line trajectory at constant velocity.
        
        Args:
            start, end: Start and end positions
            velocity: Constant velocity (m/s)
            
        Returns:
            Trajectory function
        """
        direction = end - start
        distance = np.linalg.norm(direction)
        unit_dir = direction / distance if distance > 0 else np.zeros(3)
        
        total_time = distance / velocity
        
        def trajectory(t: float) -> np.ndarray:
            if t <= 0:
                return start
            if t >= total_time:
                return end
            
            return start + unit_dir * velocity * t
        
        return trajectory
    
    def compute_velocities(self, trajectory: Callable, 
                          dt: float = 0.01,
                          num_samples: int = 1000) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute velocity and acceleration along trajectory.
        
        Returns:
            (times, velocities, accelerations)
        """
        times = np.linspace(0, num_samples * dt, num_samples)
        positions = np.array([trajectory(t) for t in times])
        
        # Compute derivatives
        velocities = np.gradient(positions, dt, axis=0)
        accelerations = np.gradient(velocities, dt, axis=0)
        
        return times, velocities, accelerations
    
    def sample_trajectory(self, trajectories: List[Callable],
                         times: List[float],
                         t: float) -> np.ndarray:
        """Sample combined trajectory at time t."""
        # Find which segment
        cumulative = np.cumsum([0] + times[:-1])
        
        for i, start_time in enumerate(cumulative):
            end_time = start_time + times[i]
            if t <= end_time:
                return trajectories[i](t - start_time)
        
        return trajectories[-1](times[-1])
    
    def emergency_stop(self, current_pos: np.ndarray,
                     current_vel: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Compute emergency stop trajectory.
        
        Returns:
            (trajectory, duration)
        """
        # Minimum distance to stop
        v = np.linalg.norm(current_vel)
        
        # decel = v^2 / (2 * distance)
        # distance = v^2 / (2 * decel)
        decel = self.a_max
        distance = v**2 / (2 * decel) if v > 0 else 0
        
        direction = -current_vel / v if v > 0 else np.zeros(3)
        
        end_pos = current_pos + direction * distance
        
        T = v / decel
        
        traj = self.line_trajectory(current_pos, end_pos, v/2)
        
        return traj, T
    
    def get_time_optimal_trajectory(self, waypoints: List[np.ndarray]) -> Tuple[List[Callable], List[float]]:
        """
        Generate time-optimal trajectory through waypoints.
        
        Returns:
            (trajectories, segment_times)
        """
        if len(waypoints) < 2:
            return [], []
        
        trajectories = []
        times = []
        
        for i in range(len(waypoints) - 1):
            p0 = waypoints[i]
            p1 = waypoints[i+1]
            
            dist = np.linalg.norm(p1 - p0)
            
            # Time based on constraints
            # v^2 = v_max^2 - 2*a_max*distance
            v_end = np.sqrt(max(0, self.v_max**2 - 2 * self.a_max * dist))
            
            # Average velocity
            v_avg = (self.v_max + v_end) / 2
            
            T = dist / v_avg if v_avg > 0 else 0.1
            
            traj = self.line_trajectory(p0, p1, v_avg)
            trajectories.append(traj)
            times.append(T)
        
        return trajectories, times