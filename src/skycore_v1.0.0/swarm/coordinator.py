"""Swarm Coordinator for multi-drone operations.

Implements:
- Formation control
- Task allocation
- Collision avoidance
- Communication relay
- Leader-follower and distributed architectures
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
import numpy as np
from numpy.typing import NDArray
import time


@dataclass
class DroneState:
    """State of a drone in the swarm."""
    id: int
    position: NDArray        # [x, y, z]
    velocity: NDArray       # [vx, vy, vz]
    heading: float           # radians
    battery: float           # 0-1
    status: str              # "idle", "active", "returning", "emergency"
    target: Optional[NDArray] = None


@dataclass
class SwarmConfig:
    """Swarm configuration."""
    n_drones: int = 3
    formation_type: str = "grid"  # "grid", "line", "circle", "custom"
    formation_spacing: float = 2.0  # meters
    max_speed: float = 5.0
        
    # Communication
    comm_range: float = 100.0
    comm_delay: float = 0.05
        
    # Safety
    min_separation: float = 1.5
    collision_warning_dist: float = 3.0
    
    # Task allocation
    task_timeout: float = 30.0


class FormationController:
    """Control swarm formation."""
    
    FORMATIONS = {
        "grid": lambda n: _grid_formation(n),
        "line": lambda n: _line_formation(n),
        "circle": lambda n: _circle_formation(n),
    }
    
    def __init__(self, config: Optional[SwarmConfig] = None):
        self.config = config or SwarmConfig()
        self.formation_offsets: List[NDArray] = []
        self._compute_formation()
    
    def _compute_formation(self) -> None:
        """Compute formation offsets."""
        generator = self.FORMATIONS.get(
            self.config.formation_type,
            lambda n: _grid_formation(n)
        )
        self.formation_offsets = generator(self.config.n_drones)
    
    def set_formation_type(self, formation_type: str) -> None:
        """Change formation type."""
        self.config.formation_type = formation_type
        self._compute_formation()
    
    def get_formation_position(self, drone_id: int, center: NDArray) -> NDArray:
        """Get target position for drone in formation."""
        if drone_id < len(self.formation_offsets):
            return center + self.formation_offsets[drone_id]
        return center
    
    def get_formation_positions(self, center: NDArray) -> List[NDArray]:
        """Get all formation positions."""
        return [center + offset for offset in self.formation_offsets]


def _grid_formation(n: int) -> List[NDArray]:
    """Generate grid formation offsets."""
    offsets = []
    cols = int(np.ceil(np.sqrt(n)))
    spacing = 2.0
    
    for i in range(n):
        row = i // cols
        col = i % cols
        offsets.append(np.array([col * spacing, row * spacing, 0]))
    
    return offsets


def _line_formation(n: int) -> List[NDArray]:
    """Generate line formation offsets."""
    offsets = []
    spacing = 2.0
    
    for i in range(n):
        offsets.append(np.array([i * spacing - (n - 1) * spacing / 2, 0, 0]))
    
    return offsets


def _circle_formation(n: int) -> List[NDArray]:
    """Generate circular formation offsets."""
    offsets = []
    radius = 3.0
    
    for i in range(n):
        angle = 2 * np.pi * i / n
        offsets.append(np.array([
            radius * np.cos(angle),
            radius * np.sin(angle),
            0
        ]))
    
    return offsets


class TaskAllocator:
    """Allocate tasks to swarm drones."""
    
    def __init__(self, config: Optional[SwarmConfig] = None):
        self.config = config or SwarmConfig()
        self.tasks: List[Dict] = []
        self.assignments: Dict[int, int] = {}  # drone_id -> task_id
    
    def add_task(
        self,
        task_id: int,
        position: NDArray,
        priority: int = 1,
        required_agents: int = 1
    ) -> None:
        """Add a task to the queue."""
        self.tasks.append({
            'id': task_id,
            'position': position,
            'priority': priority,
            'required_agents': required_agents,
            'created_time': time.time(),
            'status': 'pending'
        })
    
    def allocate(
        self,
        drones: List[DroneState],
        time_now: float
    ) -> Dict[int, NDArray]:
        """Allocate tasks to drones.
        
        Returns:
            Dictionary mapping drone_id to target position
        """
        assignments = {}
        
        # Sort tasks by priority
        sorted_tasks = sorted(
            [t for t in self.tasks if t['status'] == 'pending'],
            key=lambda x: (-x['priority'], x['created_time'])
        )
        
        # Available drones
        available = [d for d in drones if d.status == "idle"]
        
        for task in sorted_tasks:
            for drone in available:
                if drone.id in assignments:
                    continue
                
                # Check if drone can reach in time
                dist = np.linalg.norm(drone.position - task['position'])
                eta = dist / self.config.max_speed
                
                if eta < self.config.task_timeout:
                    assignments[drone.id] = task['position']
                    drone.status = "active"
                    drone.target = task['position']
                    break
        
        return assignments
    
    def update_tasks(self, drones: List[DroneState]) -> None:
        """Update task status based on drone positions."""
        for drone in drones:
            if drone.target is not None:
                dist = np.linalg.norm(drone.position - drone.target)
                if dist < 1.0:  # Task completed
                    # Find and mark task complete
                    for task in self.tasks:
                        if np.allclose(task['position'], drone.target):
                            task['status'] = 'completed'
                            break
                    drone.target = None
                    drone.status = "idle"


class CollisionAvoidance:
    """Prevent collisions in swarm."""
    
    def __init__(self, config: Optional[SwarmConfig] = None):
        self.config = config or SwarmConfig()
    
    def check(
        self,
        drone_pos: NDArray,
        other_positions: List[NDArray],
        velocities: List[NDArray]
    ) -> Tuple[bool, Optional[NDArray]]:
        """Check for potential collision and compute avoidance.
        
        Returns:
            (collision_risk, avoidance_vector)
        """
        avoidance = np.zeros(3)
        
        for other_pos, other_vel in zip(other_positions, velocities):
            # Relative position and velocity
            rel_pos = drone_pos - other_pos
            rel_vel = np.zeros(3) - other_vel  # Assuming self is stationary for now
            
            dist = np.linalg.norm(rel_pos)
            
            # Check if approaching
            approach = np.dot(rel_pos, rel_vel)
            
            if dist < self.config.collision_warning_dist and approach < 0:
                # Need to avoid
                # Push away from other drone
                if dist > 0.1:
                    avoidance_dir = rel_pos / dist
                    # Weight by inverse distance
                    weight = 1.0 / (dist + 0.1)
                    avoidance += avoidance_dir * weight * (self.config.collision_warning_dist - dist)
            
            # Hard minimum separation
            if dist < self.config.min_separation:
                avoidance += (rel_pos / dist) * (self.config.min_separation - dist)
        
        # Normalize and scale
        avoidance_mag = np.linalg.norm(avoidance)
        
        if avoidance_mag > 0.1:
            return True, (avoidance / avoidance_mag) * self.config.max_speed
        elif avoidance_mag > 0:
            return True, avoidance
        else:
            return False, None
    
    def compute_safe_velocity(
        self,
        current_pos: NDArray,
        desired_vel: NDArray,
        other_drones: List[DroneState],
        look_ahead: float = 1.0
    ) -> NDArray:
        """Compute safe velocity that avoids collisions."""
        safe_vel = desired_vel.copy()
        
        for other in other_drones:
            # Predict future position
            future_pos = other.position + other.velocity * look_ahead
            
            # Vector to other drone
            to_other = future_pos - current_pos
            dist = np.linalg.norm(to_other)
            
            if dist < self.config.collision_warning_dist:
                # Push away
                if dist > 0.1:
                    push = -to_other / dist
                    safe_vel += push * 0.5
        
        # Limit to max speed
        speed = np.linalg.norm(safe_vel)
        if speed > self.config.max_speed:
            safe_vel = (safe_vel / speed) * self.config.max_speed
        
        return safe_vel


class SwarmCoordinator:
    """Main swarm coordinator."""
    
    def __init__(self, config: Optional[SwarmConfig] = None):
        self.config = config or SwarmConfig()
        
        self.formation = FormationController(config)
        self.allocator = TaskAllocator(config)
        self.collision_avoidance = CollisionAvoidance(config)
        
        # Leader drone
        self.leader_id: Optional[int] = None
        self.leader_position: Optional[NDArray] = None
        
        # Drone states
        self.drones: Dict[int, DroneState] = {}
        for i in range(config.n_drones):
            self.drones[i] = DroneState(
                id=i,
                position=np.array([0, 0, 0]),
                velocity=np.zeros(3),
                heading=0,
                battery=1.0,
                status="idle"
            )
        
        # Communication graph
        self.adjacency: Dict[int, List[int]] = {}
        self._update_connectivity()
    
    def update_drone_state(
        self,
        drone_id: int,
        position: NDArray,
        velocity: NDArray,
        battery: float
    ) -> None:
        """Update state of a drone."""
        if drone_id in self.drones:
            self.drones[drone_id].position = position
            self.drones[drone_id].velocity = velocity
            self.drones[drone_id].battery = battery
            
            # Update heading
            if np.linalg.norm(velocity) > 0.1:
                self.drones[drone_id].heading = np.arctan2(velocity[1], velocity[0])
    
    def set_leader(self, drone_id: int) -> None:
        """Set leader drone."""
        self.leader_id = drone_id
    
    def update_leader_position(self, position: NDArray) -> None:
        """Update leader position for formation tracking."""
        self.leader_position = position
    
    def compute_targets(self) -> Dict[int, NDArray]:
        """Compute target positions for all drones.
        
        Returns:
            Dictionary of drone_id -> target position
        """
        targets = {}
        
        # Get all drone states
        drone_list = list(self.drones.values())
        
        # Update task allocator
        self.allocator.update_tasks(drone_list)
        
        # Get task assignments
        task_targets = self.allocator.allocate(drone_list, time.time())
        
        # Formation positions
        center = self.leader_position if self.leader_position is not None else np.zeros(3)
        
        # Check collision avoidance for each drone
        for drone_id, drone in self.drones.items():
            # Determine if drone has task assignment
            if drone_id in task_targets:
                target = task_targets[drone_id]
            else:
                # Use formation position
                target = self.formation.get_formation_position(drone_id, center)
            
            # Check collisions
            other_positions = [self.drones[i].position for i in self.drones if i != drone_id]
            other_velocities = [self.drones[i].velocity for i in self.drones if i != drone_id]
            
            collision, avoidance = self.collision_avoidance.check(
                drone.position, other_positions, other_velocities
            )
            
            if collision and avoidance is not None:
                # Apply avoidance offset
                targets[drone_id] = drone.position + avoidance * 0.5
            else:
                targets[drone_id] = target
        
        return targets
    
    def _update_connectivity(self) -> None:
        """Update communication adjacency based on positions."""
        for drone_id in self.drones:
            connected = []
            for other_id, other in self.drones.items():
                if drone_id == other_id:
                    continue
                dist = np.linalg.norm(
                    self.drones[drone_id].position - other.position
                )
                if dist < self.config.comm_range:
                    connected.append(other_id)
            self.adjacency[drone_id] = connected
    
    def get_communication_topology(self) -> List[Tuple[int, int]]:
        """Get list of communication links for visualization."""
        links = []
        seen = set()
        
        for drone_id, connected in self.adjacency.items():
            for other_id in connected:
                link = tuple(sorted([drone_id, other_id]))
                if link not in seen:
                    links.append(link)
                    seen.add(link)
        
        return links
    
    def assign_reconnaissance(
        self,
        points: List[NDArray]
    ) -> Dict[int, NDArray]:
        """Assign reconnaissance points to drones."""
        assignments = {}
        
        # Simple round-robin assignment
        for i, point in enumerate(points):
            drone_id = i % self.config.n_drones
            assignments[drone_id] = point
            self.drones[drone_id].target = point
            self.drones[drone_id].status = "active"
        
        return assignments
    
    def handle_emergency(
        self,
        emergency_drone_id: int
    ) -> Dict[int, NDArray]:
        """Handle emergency for a drone by redistributing tasks."""
        emergency_drone = self.drones[emergency_drone_id]
        emergency_drone.status = "emergency"
        
        # Find nearby drone to take over
        nearby = None
        min_dist = float('inf')
        
        for drone_id, drone in self.drones.items():
            if drone_id == emergency_drone_id:
                continue
            if drone.status != "idle":
                continue
            
            dist = np.linalg.norm(emergency_drone.position - drone.position)
            if dist < min_dist:
                min_dist = dist
                nearby = drone_id
        
        if nearby is not None:
            # Transfer target
            if emergency_drone.target is not None:
                self.drones[nearby].target = emergency_drone.target
                self.drones[nearby].status = "active"
        
        return {}


def demo_swarm():
    """Demonstrate swarm coordination."""
    print("=" * 60)
    print("Swarm Coordinator Demo")
    print("=" * 60)
    
    # Create swarm
    config = SwarmConfig(n_drones=4, formation_type="grid", formation_spacing=2.0)
    swarm = SwarmCoordinator(config)
    
    # Set up drones
    initial_positions = [
        np.array([0, 0, 5]),
        np.array([10, 0, 5]),
        np.array([0, 10, 5]),
        np.array([10, 10, 5])
    ]
    
    for i, pos in enumerate(initial_positions):
        swarm.update_drone_state(i, pos, np.zeros(3), 0.8)
    
    # Set leader
    swarm.set_leader(0)
    swarm.update_leader_position(initial_positions[0])
    
    print("\nInitial drone positions:")
    for drone in swarm.drones.values():
        print(f"  Drone {drone.id}: {drone.position}")
    
    # Compute formation targets
    print("\nFormation targets (leader at origin):")
    targets = swarm.compute_targets()
    for drone_id, target in targets.items():
        print(f"  Drone {drone_id}: {target}")
    
    # Add tasks
    print("\nAssigning reconnaissance tasks...")
    recon_points = [
        np.array([50, 50, 10]),
        np.array([60, 40, 10]),
        np.array([40, 60, 10])
    ]
    assignments = swarm.assign_reconnaissance(recon_points)
    
    for drone_id, point in assignments.items():
        print(f"  Drone {drone_id} -> {point}")
    
    # Test collision avoidance
    print("\nCollision avoidance test:")
    # Move drone 1 and 2 close together
    swarm.update_drone_state(1, np.array([15, 15, 5]), np.zeros(3), 0.8)
    swarm.update_drone_state(2, np.array([16, 15, 5]), np.zeros(3), 0.8)
    
    collision, avoidance = swarm.collision_avoidance.check(
        swarm.drones[1].position,
        [swarm.drones[2].position],
        [swarm.drones[2].velocity]
    )
    print(f"  Collision risk: {collision}")
    if avoidance is not None:
        print(f"  Avoidance vector: {avoidance}")
    
    # Communication topology
    print("\nCommunication links:")
    links = swarm.get_communication_topology()
    for link in links:
        print(f"  {link[0]} <-> {link[1]}")


if __name__ == "__main__":
    demo_swarm()