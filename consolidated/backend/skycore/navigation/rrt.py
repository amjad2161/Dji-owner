"""
SkyCore RRT* Path Planner
========================
Rapidly-exploring Random Tree with RRT*-style rewiring for drone navigation.

Note: plan() terminates at the FIRST collision-free solution (with local rewiring),
so paths are near-optimal but not asymptotically optimal in the strict RRT* sense.
Edges are collision-checked, so the tree itself respects obstacle clearance.
"""

import numpy as np
from typing import List, Tuple, Dict, Optional, Callable
import logging
import random
import time

log = logging.getLogger(__name__)


class RRTStarNode:
    """RRT* tree node."""
    def __init__(self, pos: np.ndarray, parent: Optional['RRTStarNode'] = None, 
                 cost: float = 0.0):
        self.pos = pos
        self.parent = parent
        self.cost = cost
        self.children = []
    
    def __repr__(self):
        return f"RRTNode({self.pos}, cost={self.cost:.2f})"


class RRTStarPlanner:
    """
    RRT* Path Planner for drone navigation.
    
    Features:
    - Cost-based (near-optimal) path planning, first-solution termination
    - Collision-checked obstacle avoidance (nodes AND edges)
    - Path smoothing
    - Dynamic replanning
    """
    
    def __init__(self, bounds: Tuple[float, float, float, float, float, float],
                 max_altitude: float = 120):
        """
        Initialize RRT* planner.
        
        Args:
            bounds: (xmin, xmax, ymin, ymax, zmin, zmax)
            max_altitude: Maximum altitude in meters
        """
        self.bounds = bounds
        self.max_altitude = max_altitude
        
        self.nodes: List[RRTStarNode] = []
        self.start: Optional[RRTStarNode] = None
        self.goal: Optional[RRTStarNode] = None
        
        # Parameters
        self.step_size = 5.0  # meters
        self.max_nodes = 5000
        self.rewire_radius = 10.0  # meters
        self.goal_bias = 0.1  # 10% chance to sample goal directly
        self.min_clearance = 2.0  # meters from obstacles
        
        # Obstacles (list of (cx, cy, cz, radius))
        self.obstacles: List[Tuple[float, float, float, float]] = []
        
        # Cost function (can be customized)
        self.cost_function: Optional[Callable] = None
    
    def add_obstacle(self, cx: float, cy: float, cz: float, radius: float):
        """Add spherical obstacle."""
        self.obstacles.append((cx, cy, cz, radius))
    
    def add_box_obstacle(self, corners: Tuple[float, float, float, float, float, float]):
        """Add box obstacle (xmin, xmax, ymin, ymax, zmin, zmax)."""
        cx = (corners[0] + corners[1]) / 2
        cy = (corners[2] + corners[3]) / 2
        cz = (corners[4] + corners[5]) / 2
        dx = (corners[1] - corners[0]) / 2
        dy = (corners[3] - corners[2]) / 2
        dz = (corners[5] - corners[4]) / 2
        radius = np.sqrt(dx**2 + dy**2 + dz**2)
        self.obstacles.append((cx, cy, cz, radius))
    
    def clear_obstacles(self):
        """Clear all obstacles."""
        self.obstacles.clear()
    
    def set_cost_function(self, cost_fn: Callable):
        """Set custom cost function."""
        self.cost_function = cost_fn
    
    def plan(self, start: Tuple[float, float, float],
             goal: Tuple[float, float, float],
             max_time: float = 10.0) -> List[Tuple[float, float, float]]:
        """
        Plan path from start to goal.
        
        Args:
            start: Start position (x, y, z)
            goal: Goal position (x, y, z)
            max_time: Maximum planning time (seconds)
            
        Returns:
            List of waypoints [(x, y, z), ...]
        """
        self.nodes.clear()
        
        # Create start and goal nodes
        start_pos = np.array(start)
        goal_pos = np.array(goal)
        
        self.start = RRTStarNode(start_pos)
        self.goal = RRTStarNode(goal_pos)
        
        self.nodes.append(self.start)
        
        # RRT* iterations
        start_time = time.time()
        iterations = 0

        while len(self.nodes) < self.max_nodes:
            # Check timeout (wall-clock budget) and a hard iteration cap
            iterations += 1
            if iterations > 10000 or (time.time() - start_time) > max_time:
                break

            # Sample random point
            if random.random() < self.goal_bias:
                sample = goal_pos
            else:
                sample = self._sample_random()

            # Find nearest node
            nearest = self._nearest_node(sample)

            # Steer towards sample
            new_pos = self._steer(nearest.pos, sample)

            # Check if new position is valid
            if not self._is_valid(new_pos):
                continue

            # Find nearby nodes for rewiring
            nearby = self._near_nodes(new_pos, self.rewire_radius)

            # Choose the min-cost parent whose EDGE to new_pos is collision-free.
            # Checking only endpoints (as before) lets a straight edge clip an
            # obstacle between two valid points; edge-checking makes the tree itself
            # obstacle-free rather than relying on a caller-side clearance pad.
            best_parent = None
            best_cost = float('inf')
            for node in [nearest] + [n for n in nearby if n is not nearest]:
                if not self._line_clear(tuple(node.pos), tuple(new_pos)):
                    continue
                cost = self._cost_to_node(node) + self._distance(node.pos, new_pos)
                if cost < best_cost:
                    best_parent = node
                    best_cost = cost
            if best_parent is None:
                continue                        # no collision-free connection to the tree

            # Create new node
            new_node = RRTStarNode(new_pos, best_parent, best_cost)
            best_parent.children.append(new_node)
            self.nodes.append(new_node)

            # Rewire nearby nodes (only through a collision-free edge)
            for node in nearby:
                new_cost = best_cost + self._distance(new_pos, node.pos)
                if new_cost < node.cost and self._line_clear(tuple(new_pos), tuple(node.pos)):
                    node.parent = new_node
                    node.cost = new_cost
                    new_node.children.append(node)
                    self._update_children_cost(node)

            # Check if goal reached (with a clear final edge)
            if (self._distance(new_pos, goal_pos) < self.step_size
                    and self._line_clear(tuple(new_pos), tuple(goal_pos))):
                self.goal.parent = new_node
                self.goal.cost = new_node.cost + self._distance(new_pos, goal_pos)
                self.goal.pos = goal_pos
                new_node.children.append(self.goal)
                break
        
        # Extract path
        path = self._extract_path()
        
        # Smooth path
        smoothed = self._smooth_path(path)
        
        log.info(f"RRT* planned path with {len(path)} nodes, {len(smoothed)} after smoothing")
        
        return smoothed if smoothed else [start, goal]
    
    def _sample_random(self) -> np.ndarray:
        """Sample random point in bounds."""
        return np.array([
            random.uniform(self.bounds[0], self.bounds[1]),
            random.uniform(self.bounds[2], self.bounds[3]),
            random.uniform(max(0, self.bounds[4]), min(self.max_altitude, self.bounds[5]))
        ])
    
    def _distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """Euclidean distance."""
        return np.linalg.norm(a - b)
    
    def _nearest_node(self, pos: np.ndarray) -> RRTStarNode:
        """Find nearest node to position."""
        return min(self.nodes, key=lambda n: self._distance(n.pos, pos))
    
    def _near_nodes(self, pos: np.ndarray, radius: float) -> List[RRTStarNode]:
        """Find nodes within radius."""
        return [n for n in self.nodes if self._distance(n.pos, pos) <= radius]
    
    def _steer(self, from_pos: np.ndarray, to_pos: np.ndarray) -> np.ndarray:
        """Steer from one position towards another."""
        direction = to_pos - from_pos
        dist = np.linalg.norm(direction)
        
        if dist <= self.step_size:
            return to_pos
        
        return from_pos + (direction / dist) * self.step_size
    
    def _is_valid(self, pos: np.ndarray) -> bool:
        """Check if position is valid (not in collision)."""
        # Check bounds
        if not (self.bounds[0] <= pos[0] <= self.bounds[1] and
                self.bounds[2] <= pos[1] <= self.bounds[3] and
                0 <= pos[2] <= self.max_altitude):
            return False
        
        # Check obstacles
        for cx, cy, cz, radius in self.obstacles:
            dist = self._distance(pos, np.array([cx, cy, cz]))
            if dist < radius + self.min_clearance:
                return False
        
        return True
    
    def _cost_to_node(self, node: RRTStarNode) -> float:
        """Calculate cost from root to node."""
        if self.cost_function:
            return self.cost_function(node.pos)
        return node.cost
    
    def _update_children_cost(self, node: RRTStarNode):
        """Recursively update children costs."""
        for child in node.children:
            child.cost = node.cost + self._distance(node.pos, child.pos)
            self._update_children_cost(child)
    
    def _extract_path(self) -> List[Tuple[float, float, float]]:
        """Extract path from start to goal."""
        path = []
        current = self.goal
        
        while current is not None:
            path.append(tuple(current.pos))
            current = current.parent
        
        path.reverse()
        return path
    
    def _smooth_path(self, path: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        """Smooth path using shortcut method."""
        if len(path) <= 2:
            return path
        
        smoothed = [path[0]]
        i = 0
        
        while i < len(path) - 1:
            # Try to skip nodes
            j = len(path) - 1
            while j > i + 1:
                if self._line_clear(path[i], path[j]):
                    break
                j -= 1
            
            smoothed.append(path[j])
            i = j
        
        return smoothed
    
    def _line_clear(self, p1: Tuple, p2: Tuple) -> bool:
        """Check if direct line between two points is clear."""
        dist = self._distance(np.array(p1), np.array(p2))
        n_samples = max(int(dist / 1.0), 3)
        
        for t in np.linspace(0, 1, n_samples):
            pos = np.array(p1) + t * (np.array(p2) - np.array(p1))
            if not self._is_valid(pos):
                return False
        
        return True
    
    def get_tree(self) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Get tree edges for visualization."""
        edges = []
        for node in self.nodes:
            if node.parent is not None:
                edges.append((node.parent.pos, node.pos))
        return edges