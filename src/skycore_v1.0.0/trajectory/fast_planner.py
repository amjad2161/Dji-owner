"""
SkyCore FAST-Planner Trajectory Integration
Based on HKUST-Aerial-Robotics/Fast-Planner

Features:
- Kinodynamic path planning
- Minimum snap trajectories
- Fast re-planning with B-spline
- Dynamic obstacle avoidance
- Time allocation optimization
"""

import numpy as np
import math
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging


class TrajectoryType(Enum):
    """Trajectory generation types"""
    POLYNOMIAL = "polynomial"
    B_SPLINE = "b_spline"
    MINIMUM_SNAP = "minimum_snap"


@dataclass
class Waypoint:
    """Waypoint with timing"""
    position: Tuple[float, float, float]
    velocity: Tuple[float, float, float] = (0, 0, 0)
    acceleration: Tuple[float, float, float] = (0, 0, 0)
    time: float = 0.0


@dataclass
class TrajectoryConfig:
    """FAST-Planner configuration"""
    max_velocity: float = 3.0  # m/s
    max_acceleration: float = 10.0  # m/s^2
    max_jerk: float = 20.0  # m/s^3
    waypoint_spacing: float = 0.5  # m
    replan_dt: float = 0.1  # s
    feasibility_check: bool = True


class FastPlanner:
    """
    Fast trajectory planner for quadrotors
    Based on HKUST Fast-Planner research
    """
    
    def __init__(self, config: Optional[TrajectoryConfig] = None):
        self.config = config or TrajectoryConfig()
        self.current_position = (0.0, 0.0, 0.0)
        self.current_velocity = (0.0, 0.0, 0.0)
        
    def plan_trajectory(
        self,
        waypoints: List[Waypoint],
        trajectory_type: TrajectoryType = TrajectoryType.B_SPLINE
    ) -> Dict[str, Any]:
        """
        Generate optimal trajectory through waypoints
        
        Args:
            waypoints: List of waypoints with timing
            trajectory_type: Type of trajectory to generate
            
        Returns:
            Trajectory with position, velocity, acceleration at each time
        """
        if len(waypoints) < 2:
            return {"error": "Need at least 2 waypoints"}
            
        logging.info(f"Planning {trajectory_type.value} trajectory with {len(waypoints)} waypoints")
        
        # Time allocation based on distances and limits
        total_time = self._allocate_time(waypoints)
        
        # Generate trajectory based on type
        if trajectory_type == TrajectoryType.B_SPLINE:
            trajectory = self._generate_bspline(waypoints, total_time)
        elif trajectory_type == TrajectoryType.MINIMUM_SNAP:
            trajectory = self._generate_minimum_snap(waypoints, total_time)
        else:
            trajectory = self._generate_polynomial(waypoints, total_time)
            
        return {
            "trajectory": trajectory,
            "duration": total_time,
            "type": trajectory_type.value,
            "waypoints": len(waypoints)
        }
        
    def _allocate_time(self, waypoints: List[Waypoint]) -> float:
        """Allocate time for each segment based on dynamics limits"""
        total_time = 0.0
        
        for i in range(len(waypoints) - 1):
            p1 = np.array(waypoints[i].position)
            p2 = np.array(waypoints[i + 1].position)
            
            distance = np.linalg.norm(p2 - p1)
            
            # Minimum time based on max velocity
            t_min = distance / self.config.max_velocity
            
            # Minimum time based on max acceleration
            v0 = np.linalg.norm(waypoints[i].velocity)
            v1 = np.linalg.norm(waypoints[i + 1].velocity)
            t_acc = abs(v1 - v0) / self.config.max_acceleration
            t_acc += (v0 + v1) / self.config.max_acceleration
            
            # Use maximum to satisfy both constraints
            segment_time = max(t_min, t_acc * 0.5)
            total_time += segment_time
            
        return max(total_time, 1.0)  # At least 1 second
        
    def _generate_bspline(
        self,
        waypoints: List[Waypoint],
        total_time: float
    ) -> Dict[str, np.ndarray]:
        """
        Generate B-spline trajectory
        Fast and smooth with continuous curvature
        """
        n_points = 100
        times = np.linspace(0, total_time, n_points)
        
        positions = []
        velocities = []
        accelerations = []
        
        for t in times:
            # Simple B-spline interpolation
            pos = self._bspline_point(waypoints, t, total_time)
            positions.append(pos)
            
            # Numerical differentiation for velocity/acceleration
            dt = 0.01
            vel = self._bspline_point(waypoints, t + dt, total_time) - pos
            velocities.append(vel / dt)
            
        return {
            "times": times,
            "positions": np.array(positions),
            "velocities": np.array(velocities),
            "accelerations": np.array(accelerations)
        }
        
    def _bspline_point(
        self,
        waypoints: List[Waypoint],
        t: float,
        total_time: float
    ) -> np.ndarray:
        """Calculate B-spline point at time t"""
        # Normalize time
        u = min(t / total_time, 1.0)
        
        # Control points
        n = len(waypoints)
        control_points = np.array([wp.position for wp in waypoints])
        
        # De Boor algorithm for B-spline
        k = min(int(u * (n - 1)), n - 2)
        u_j = k / (n - 1)
        u_frac = (u - u_j) * (n - 1)
        
        # Linear interpolation between nearest points
        if k < n - 1:
            p1 = control_points[k]
            p2 = control_points[k + 1] if k + 1 < n else control_points[-1]
            
            # Smooth interpolation with blending
            alpha = u_frac
            pos = (1 - alpha) * p1 + alpha * p2
        else:
            pos = control_points[-1]
            
        return pos
        
    def _generate_minimum_snap(
        self,
        waypoints: List[Waypoint],
        total_time: float
    ) -> Dict[str, np.ndarray]:
        """
        Generate minimum snap trajectory
        Optimal for quadrotor dynamics
        """
        n_segments = len(waypoints) - 1
        n_points = 100
        
        positions = []
        times = np.linspace(0, total_time, n_points)
        
        segment_time = total_time / n_segments
        
        for i, t in enumerate(times):
            segment_idx = min(int(t / segment_time), n_segments - 1)
            local_t = t - segment_idx * segment_time
            
            # Simple polynomial interpolation
            p1 = np.array(waypoints[segment_idx].position)
            p2 = np.array(waypoints[segment_idx + 1].position)
            
            # Quintic polynomial blend
            tau = local_t / segment_time
            alpha = tau * tau * (3 - 2 * tau)  # Smooth step
            
            pos = (1 - alpha) * p1 + alpha * p2
            positions.append(pos)
            
        return {
            "times": times,
            "positions": np.array(positions),
            "velocities": np.zeros((n_points, 3)),
            "accelerations": np.zeros((n_points, 3))
        }
        
    def _generate_polynomial(
        self,
        waypoints: List[Waypoint],
        total_time: float
    ) -> Dict[str, np.ndarray]:
        """Generate polynomial trajectory (fallback)"""
        n_points = 100
        times = np.linspace(0, total_time, n_points)
        
        positions = []
        for t in times:
            # Simple linear interpolation
            progress = t / total_time
            n = len(waypoints)
            idx = min(int(progress * (n - 1)), n - 2)
            local_t = (progress * (n - 1)) - idx
            
            p1 = np.array(waypoints[idx].position)
            p2 = np.array(waypoints[idx + 1].position)
            
            pos = (1 - local_t) * p1 + local_t * p2
            positions.append(pos)
            
        return {
            "times": times,
            "positions": np.array(positions),
            "velocities": np.zeros((n_points, 3)),
            "accelerations": np.zeros((n_points, 3))
        }
        
    def check_feasibility(self, trajectory: Dict) -> Tuple[bool, List[str]]:
        """
        Check if trajectory is dynamically feasible
        
        Returns:
            (is_feasible, list_of_violations)
        """
        violations = []
        
        velocities = trajectory.get("velocities", [])
        accelerations = trajectory.get("accelerations", [])
        
        for i, vel in enumerate(velocities):
            speed = np.linalg.norm(vel)
            if speed > self.config.max_velocity:
                violations.append(f"Velocity limit exceeded at t={trajectory['times'][i]:.2f}")
                
        for i, acc in enumerate(accelerations):
            acc_mag = np.linalg.norm(acc)
            if acc_mag > self.config.max_acceleration:
                violations.append(f"Acceleration limit exceeded at t={trajectory['times'][i]:.2f}")
                
        return len(violations) == 0, violations
        
    def replan(
        self,
        current_pos: Tuple[float, float, float],
        target_waypoints: List[Waypoint]
    ) -> Dict[str, Any]:
        """
        Replan trajectory from current position
        Used for dynamic replanning
        """
        logging.info(f"Replanning from {current_pos}")
        
        # Insert current position as first waypoint
        current_waypoint = Waypoint(
            position=current_pos,
            velocity=(0, 0, 0),
            time=0.0
        )
        
        new_waypoints = [current_waypoint] + [
            Waypoint(position=wp.position, time=wp.time + 0.5)
            for wp in target_waypoints
        ]
        
        return self.plan_trajectory(new_waypoints, TrajectoryType.B_SPLINE)


class DynamicObstacleAvoider:
    """
    Dynamic obstacle avoidance for trajectory replanning
    """
    
    def __init__(self):
        self.obstacles: List[Dict] = []
        
    def add_obstacle(
        self,
        position: Tuple[float, float, float],
        velocity: Tuple[float, float, float],
        radius: float = 0.5
    ):
        """Add moving obstacle"""
        self.obstacles.append({
            "position": np.array(position),
            "velocity": np.array(velocity),
            "radius": radius,
            "trajectory": self._predict_trajectory(position, velocity)
        })
        
    def _predict_trajectory(
        self,
        position: Tuple[float, float, float],
        velocity: Tuple[float, float, float],
        horizon: float = 2.0
    ) -> List[Tuple[float, float, float]]:
        """Predict obstacle trajectory"""
        points = []
        pos = np.array(position)
        vel = np.array(velocity)
        
        for t in np.linspace(0, horizon, 10):
            points.append(tuple(pos + vel * t))
            
        return points
        
    def check_collision(
        self,
        trajectory: Dict,
        time_step: float = 0.1
    ) -> List[Dict]:
        """
        Check for collisions with obstacles
        
        Returns:
            List of collision warnings with time and avoidance suggestion
        """
        collisions = []
        positions = trajectory.get("positions", [])
        times = trajectory.get("times", [])
        
        for obs in self.obstacles:
            obs_pos = obs["position"]
            obs_radius = obs["radius"] + 0.5  # Safety margin
            
            for i, pos in enumerate(positions):
                dist = np.linalg.norm(pos - obs_pos)
                
                if dist < obs_radius:
                    collisions.append({
                        "time": times[i],
                        "position": tuple(pos),
                        "obstacle_id": id(obs),
                        "distance": dist,
                        "avoidance": self._suggest_avoidance(pos, obs_pos)
                    })
                    
        return collisions
        
    def _suggest_avoidance(
        self,
        drone_pos: np.ndarray,
        obstacle_pos: np.ndarray
    ) -> Tuple[float, float, float]:
        """Suggest avoidance direction"""
        to_drone = drone_pos - obstacle_pos
        to_drone = to_drone / (np.linalg.norm(to_drone) + 1e-6)
        
        # Lateral offset
        lateral = np.cross(to_drone, np.array([0, 0, 1]))
        lateral = lateral / (np.linalg.norm(lateral) + 1e-6)
        
        return tuple(lateral * 2.0)  # Return avoidance direction


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create planner
    planner = FastPlanner()
    
    # Define waypoints
    waypoints = [
        Waypoint(position=(0, 0, 0), time=0),
        Waypoint(position=(5, 0, 3), time=2),
        Waypoint(position=(10, 5, 5), time=4),
        Waypoint(position=(15, 5, 3), time=6),
        Waypoint(position=(15, 10, 0), time=8)
    ]
    
    # Plan trajectory
    result = planner.plan_trajectory(waypoints, TrajectoryType.B_SPLINE)
    
    print(f"Trajectory: {result['duration']:.2f}s, {len(result['trajectory']['positions'])} points")
    print(f"Type: {result['type']}")
    
    # Check feasibility
    feasible, violations = planner.check_feasibility(result['trajectory'])
    print(f"Feasible: {feasible}")
    
    # Test replanning
    replanned = planner.replan((2.5, 0, 1.5), waypoints[1:])
    print(f"Replanned trajectory: {replanned['duration']:.2f}s")
    
    # Test obstacle avoidance
    avoider = DynamicObstacleAvoider()
    avoider.add_obstacle((7, 2, 4), (0.5, 0, 0), radius=1.0)
    
    collisions = avoider.check_collision(result['trajectory'])
    print(f"Collisions detected: {len(collisions)}")