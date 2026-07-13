"""
SkyCore Swarm Coordinator Enhanced
Based on TelloSwarm (IEEE ICUAS 2022) - formation control and multi-UAV coordination

Features:
- Formation control (line, grid, circle, V-shape)
- Decentralized coordination
- Collision avoidance
- Leader-follower and distributed architectures
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import math


@dataclass
class SwarmAgent:
    """Single drone in the swarm"""
    id: int
    position: np.ndarray  # [x, y, z] in body frame relative to formation
    velocity: np.ndarray
    state: str = "idle"
    leader: bool = False
    
    
class FormationController:
    """
    Formation control for multi-UAV swarms
    Based on consensus-based control with graph Laplacian
    """
    
    FORMATION_TYPES = {
        "line": "Linear formation",
        "grid": "Grid formation", 
        "circle": "Circular formation",
        "v_shape": "V-shape formation",
        "custom": "Custom formation"
    }
    
    def __init__(self, num_agents: int, formation_type: str = "line"):
        self.num_agents = num_agents
        self.formation_type = formation_type
        self.agents: List[SwarmAgent] = []
        self.formation_center = np.array([0.0, 0.0, 20.0])  # Center position
        self.formation_spacing = 3.0  # meters between agents
        
        # Communication graph (adjacency matrix)
        self.graph = self._create_communication_graph()
        
        # Formation positions
        self.formation_positions = self._generate_formation()
        
    def _create_communication_graph(self) -> np.ndarray:
        """Create communication topology between agents"""
        # Fully connected for small swarms
        if self.num_agents <= 5:
            return np.ones((self.num_agents, self.num_agents))
        
        # Ring topology for larger swarms
        graph = np.zeros((self.num_agents, self.num_agents))
        for i in range(self.num_agents):
            graph[i, (i - 1) % self.num_agents] = 1
            graph[i, (i + 1) % self.num_agents] = 1
        return graph
    
    def _generate_formation(self) -> List[np.ndarray]:
        """Generate target positions for formation"""
        positions = []
        
        if self.formation_type == "line":
            for i in range(self.num_agents):
                x = (i - self.num_agents / 2) * self.formation_spacing
                positions.append(np.array([x, 0, 0]))
                
        elif self.formation_type == "grid":
            cols = int(math.ceil(math.sqrt(self.num_agents)))
            rows = int(math.ceil(self.num_agents / cols))
            for i in range(self.num_agents):
                row = i // cols
                col = i % cols
                x = (col - cols / 2) * self.formation_spacing
                y = (row - rows / 2) * self.formation_spacing
                positions.append(np.array([x, y, 0]))
                
        elif self.formation_type == "circle":
            for i in range(self.num_agents):
                angle = 2 * math.pi * i / self.num_agents
                radius = self.num_agents * self.formation_spacing / (2 * math.pi)
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                positions.append(np.array([x, y, 0]))
                
        elif self.formation_type == "v_shape":
            for i in range(self.num_agents):
                if i == 0:
                    positions.append(np.array([0, 0, 0]))  # Leader
                else:
                    side = -1 if i % 2 == 1 else 1
                    row = (i + 1) // 2
                    x = row * self.formation_spacing
                    y = side * row * self.formation_spacing
                    positions.append(np.array([x, y, 0]))
        else:
            # Default line
            for i in range(self.num_agents):
                x = (i - self.num_agents / 2) * self.formation_spacing
                positions.append(np.array([x, 0, 0]))
                
        return positions
    
    def compute_control_inputs(
        self, 
        positions: List[np.ndarray], 
        velocities: List[np.ndarray]
    ) -> List[np.ndarray]:
        """
        Compute velocity commands for formation keeping
        Based on consensus protocol: dot(x_i) = sum(a_ij * (x_j - x_i))
        
        Args:
            positions: Current positions of all agents
            velocities: Current velocities of all agents
            
        Returns:
            List of velocity commands for each agent
        """
        commands = []
        
        for i in range(self.num_agents):
            # Desired position from formation
            desired = self.formation_center + self.formation_positions[i]
            
            # Consensus term (formation keeping)
            consensus = np.zeros(3)
            for j in range(self.num_agents):
                if self.graph[i, j] == 1:
                    consensus += (positions[j] - positions[i])
            
            # Position error term
            pos_error = desired - positions[i]
            
            # Velocity consensus (match neighbor velocities)
            vel_consensus = np.zeros(3)
            for j in range(self.num_agents):
                if self.graph[i, j] == 1:
                    vel_consensus += (velocities[j] - velocities[i])
            
            # Combined control law
            # k1 * pos_error + k2 * consensus + k3 * vel_consensus
            k1, k2, k3 = 0.5, 0.3, 0.2
            cmd = k1 * pos_error + k2 * consensus + k3 * vel_consensus
            
            # Limit maximum velocity
            max_vel = 5.0  # m/s
            if np.linalg.norm(cmd) > max_vel:
                cmd = cmd / np.linalg.norm(cmd) * max_vel
                
            commands.append(cmd)
            
        return commands


class CollisionAvoidance:
    """
    Collision avoidance using velocity obstacles and potential fields
    """
    
    def __init__(self, safety_radius: float = 2.0, detection_range: float = 10.0):
        self.safety_radius = safety_radius
        self.detection_range = detection_range
        
    def check_collision(
        self, 
        pos: np.ndarray, 
        other_positions: List[np.ndarray]
    ) -> bool:
        """Check if collision is imminent"""
        for other in other_positions:
            dist = np.linalg.norm(pos - other)
            if dist < self.safety_radius:
                return True
        return False
    
    def compute_avoidance_vector(
        self, 
        pos: np.ndarray, 
        vel: np.ndarray,
        other_positions: List[np.ndarray],
        other_velocities: List[np.ndarray]
    ) -> np.ndarray:
        """
        Compute avoidance velocity using Artificial Potential Fields
        
        Args:
            pos: Current position
            vel: Current desired velocity
            other_positions: Positions of nearby drones
            other_velocities: Velocities of nearby drones
            
        Returns:
            Avoidance velocity vector
        """
        avoidance = np.zeros(3)
        
        for other_pos, other_vel in zip(other_positions, other_velocities):
            # Distance and direction to other drone
            diff = pos - other_pos
            dist = np.linalg.norm(diff)
            
            if dist < self.detection_range and dist > 0:
                # Normalized direction (repulsive)
                direction = diff / dist
                
                # Repulsive force magnitude (inverse square law)
                # F = k / r^2 for r < detection_range
                k = 10.0
                magnitude = k / (dist ** 2 + 0.1)  # +0.1 to avoid division by zero
                
                # Apply only in detection range
                if dist < self.detection_range:
                    avoidance += magnitude * direction
                    
                    # Time to collision based avoidance
                    # If other drone is approaching, increase avoidance
                    rel_vel = vel - other_vel
                    rel_dir = -diff / dist
                    approach_rate = np.dot(rel_vel, rel_dir)
                    
                    if approach_rate > 0:  # Approaching
                        ttc = dist / (np.linalg.norm(rel_vel) + 0.1)
                        if ttc < 5.0:  # Will collide within 5 seconds
                            avoidance += 2.0 * direction * (5.0 - ttc) / 5.0
        
        # Limit avoidance magnitude
        max_avoidance = 3.0  # m/s
        if np.linalg.norm(avoidance) > max_avoidance:
            avoidance = avoidance / np.linalg.norm(avoidance) * max_avoidance
            
        return avoidance
    
    def merge_with_desired(
        self, 
        desired_vel: np.ndarray, 
        avoidance_vel: np.ndarray,
        weight: float = 0.5
    ) -> np.ndarray:
        """Merge desired velocity with avoidance"""
        return (1 - weight) * desired_vel + weight * avoidance_vel


class SwarmMissionExecutor:
    """
    Execute missions across multiple drones
    """
    
    def __init__(self, num_drones: int):
        self.num_drones = num_drones
        self.formation = FormationController(num_drones)
        self.collision_avoider = CollisionAvoidance()
        self.current_waypoints: List[Dict] = []
        self.current_wp_index = 0
        
    def plan_formation_mission(
        self, 
        center_waypoints: List[Dict],
        formation_type: str = "line"
    ) -> List[List[Dict]]:
        """
        Plan mission for formation of drones
        
        Args:
            center_waypoints: Waypoints for formation center
            formation_type: Type of formation
            
        Returns:
            List of mission plans for each drone
        """
        self.formation.formation_type = formation_type
        self.formation.formation_positions = self.formation._generate_formation()
        
        missions = []
        for i in range(self.num_drones):
            drone_mission = []
            for wp in center_waypoints:
                # Offset each drone by its formation position
                offset = self.formation.formation_positions[i]
                drone_wp = {
                    "lat": wp.get("lat", 0) + offset[0] * 0.00001,  # Rough conversion
                    "lon": wp.get("lon", 0) + offset[1] * 0.00001,
                    "alt": wp.get("alt", 20) + offset[2]
                }
                drone_mission.append(drone_wp)
            missions.append(drone_mission)
            
        return missions
    
    def execute_step(
        self,
        positions: List[np.ndarray],
        velocities: List[np.ndarray],
        center_position: np.ndarray
    ) -> List[np.ndarray]:
        """
        Execute one step of swarm control
        
        Args:
            positions: Current positions of all drones
            velocities: Current velocities of all drones
            center_position: Desired position for formation center
            
        Returns:
            Velocity commands for each drone
        """
        # Update formation center
        self.formation.formation_center = center_position
        
        # Get formation control inputs
        formation_cmds = self.formation.compute_control_inputs(positions, velocities)
        
        # Add collision avoidance
        final_cmds = []
        for i in range(self.num_drones):
            # Get other drones' positions (excluding self)
            other_positions = [positions[j] for j in range(self.num_drones) if j != i]
            other_velocities = [velocities[j] for j in range(self.num_drones) if j != i]
            
            # Compute avoidance
            avoidance = self.collision_avoider.compute_avoidance_vector(
                positions[i], 
                formation_cmds[i],
                other_positions,
                other_velocities
            )
            
            # Merge
            final_cmd = self.collision_avoider.merge_with_desired(
                formation_cmds[i],
                avoidance,
                weight=0.4
            )
            
            final_cmds.append(final_cmd)
            
        return final_cmds


# Stability analysis
def analyze_swarm_stability(
    num_agents: int,
    graph_adjacency: np.ndarray
) -> Tuple[bool, float]:
    """
    Analyze swarm stability using graph Laplacian eigenvalues
    
    Args:
        num_agents: Number of agents
        graph_adjacency: Adjacency matrix
        
    Returns:
        Tuple of (is_stable, convergence_rate)
    """
    # Degree matrix
    degree = np.sum(graph_adjacency, axis=1)
    D = np.diag(degree)
    
    # Laplacian
    L = D - graph_adjacency
    
    # Eigenvalues
    eigenvalues = np.linalg.eigvals(L)
    eigenvalues = np.sort(eigenvalues.real)
    
    # Smallest non-zero eigenvalue (algebraic connectivity)
    # For stability, all eigenvalues except 0 should be positive
    if len(eigenvalues) > 1:
        algebraic_conn = eigenvalues[1]  # Second smallest
        is_stable = algebraic_conn > 0
        convergence_rate = algebraic_conn
    else:
        is_stable = True
        convergence_rate = 0
    
    return is_stable, convergence_rate


# Example usage
if __name__ == "__main__":
    # Create swarm with 5 drones
    swarm = SwarmMissionExecutor(num_drones=5)
    swarm.formation.formation_type = "v_shape"
    
    # Simulate positions
    positions = [np.array([i * 2.0, 0.0, 20.0]) for i in range(5)]
    velocities = [np.array([0.0, 0.0, 0.0]) for _ in range(5)]
    center = np.array([0.0, 0.0, 20.0])
    
    # Execute step
    cmds = swarm.execute_step(positions, velocities, center)
    
    print("Swarm Control Commands:")
    for i, cmd in enumerate(cmds):
        print(f"  Drone {i}: {cmd}")
    
    # Stability check
    is_stable, rate = analyze_swarm_stability(5, swarm.formation.graph)
    print(f"\nStability: {'Stable' if is_stable else 'Unstable'}")
    print(f"Convergence rate: {rate:.3f}")