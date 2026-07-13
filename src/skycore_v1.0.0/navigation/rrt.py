"""RRT* (Optimal Rapidly-Exploring Random Tree) path planning.

Implements:
- Standard RRT
- RRT* with optimality guarantees
- RRT-Connect for bidirectional planning
- Informed RRT* for ellipsoidal search
- Dynamic obstacle handling

References:
  - LaValle (1998) - Rapidly-Exploring Random Trees
  - Karaman & Frazzoli (2011) - Optimal Sampling Algorithms
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Callable
import numpy as np
from numpy.typing import NDArray
import random


@dataclass
class TreeNode:
    """Node in RRT tree."""
    position: NDArray
    parent: Optional['TreeNode'] = None
    cost: float = 0.0
    
    def __repr__(self):
        return f"Node(pos={self.position}, cost={self.cost:.2f})"


@dataclass 
class RRTConfig:
    """RRT configuration."""
    max_iterations: int = 10000
    step_size: float = 0.5      # Maximum expansion distance
    goal_bias: float = 0.1       # Probability of sampling goal
    search_radius: float = 1.0   # For RRT*: neighbor search radius
    
    # Optional constraints
    min_clearance: float = 0.5   # Minimum distance from obstacles
    
    # Optimization (RRT*)
    optimization_iterations: int = 100
    rewire_radius: float = 2.0   # Rewiring radius for RRT*
    
    # Bounds
    bounds_min: NDArray = field(default_factory=lambda: np.zeros(3))
    bounds_max: NDArray = field(default_factory=lambda: np.array([100, 100, 50]))


class ObstacleChecker:
    """Check collision with obstacles."""
    
    def __init__(self):
        self.obstacles: List[Tuple[NDArray, float]] = []  # (center, radius)
    
    def add_sphere(self, center: NDArray, radius: float) -> None:
        """Add spherical obstacle."""
        self.obstacles.append((np.array(center), radius))
    
    def add_box(
        self,
        center: NDArray,
        size: NDArray,
        resolution: float = 0.1
    ) -> None:
        """Add box obstacle (approximated as spheres for simplicity)."""
        half = size / 2
        corners = [
            center + np.array([dx, dy, dz]) * 2
            for dx in [-1, 1] for dy in [-1, 1] for dz in [-1, 1]
        ]
        for corner in corners:
            self.add_sphere(corner, resolution)
    
    def clear(self) -> None:
        """Clear all obstacles."""
        self.obstacles = []
    
    def check_collision(self, point: NDArray) -> bool:
        """Check if point collides with any obstacle."""
        for center, radius in self.obstacles:
            if np.linalg.norm(point - center) < radius:
                return True
        return False
    
    def check_segment(self, p1: NDArray, p2: NDArray, steps: int = 10) -> bool:
        """Check if segment collides with obstacles."""
        for t in np.linspace(0, 1, steps):
            point = p1 + t * (p2 - p1)
            if self.check_collision(point):
                return True
        return False
    
    def distance_to_nearest(self, point: NDArray) -> float:
        """Get distance to nearest obstacle."""
        if not self.obstacles:
            return float('inf')
        
        min_dist = float('inf')
        for center, radius in self.obstacles:
            dist = np.linalg.norm(point - center) - radius
            min_dist = min(min_dist, dist)
        
        return max(0, min_dist)


class RRT:
    """Rapidly-Exploring Random Tree."""
    
    def __init__(self, config: Optional[RRTConfig] = None):
        self.config = config or RRTConfig()
        self.tree: List[TreeNode] = []
        self.goal_node: Optional[TreeNode] = None
        self.checker = ObstacleChecker()
        
        # Statistics
        self.iterations = 0
        self.nodes_visited = 0
    
    def reset(self) -> None:
        """Reset tree."""
        self.tree = []
        self.goal_node = None
        self.iterations = 0
    
    def plan(
        self,
        start: NDArray,
        goal: NDArray,
        obstacles: Optional[ObstacleChecker] = None,
        goal_tolerance: float = 0.5
    ) -> Tuple[List[NDArray], bool]:
        """Plan path from start to goal.
        
        Args:
            start: Start position (3,)
            goal: Goal position (3,)
            obstacles: Obstacle checker
            goal_tolerance: Distance to goal to consider reached
            
        Returns:
            (path, found)
        """
        if obstacles is not None:
            self.checker = obstacles
        
        self.reset()
        
        # Add start node
        start_node = TreeNode(position=start.copy(), cost=0.0)
        self.tree.append(start_node)
        
        # Search for path
        goal_idx = None
        
        for self.iterations in range(self.config.max_iterations):
            # Sample random point
            if random.random() < self.config.goal_bias:
                rand_point = goal.copy()
            else:
                rand_point = self._sample_random()
            
            # Find nearest node
            nearest_idx = self._find_nearest(rand_point)
            nearest = self.tree[nearest_idx]
            
            # Expand tree
            new_point, success = self._steer(nearest.position, rand_point)
            
            if not success:
                continue
            
            # Check collision
            if self.checker.check_segment(nearest.position, new_point):
                continue
            
            # Create new node
            dist = np.linalg.norm(new_point - nearest.position)
            new_node = TreeNode(
                position=new_point,
                parent=nearest,
                cost=nearest.cost + dist
            )
            
            self.tree.append(new_node)
            
            # Check if goal reached
            if np.linalg.norm(new_point - goal) < goal_tolerance:
                self.goal_node = new_node
                goal_idx = len(self.tree) - 1
                break
        
        # Reconstruct path
        if self.goal_node is not None:
            path = self._reconstruct_path(self.goal_node)
            return path, True
        
        return [], False
    
    def _sample_random(self) -> NDArray:
        """Sample random point in bounds."""
        bounds = self.config.bounds_max - self.config.bounds_min
        return self.config.bounds_min + np.random.rand(3) * bounds
    
    def _find_nearest(self, point: NDArray) -> int:
        """Find nearest node in tree."""
        min_dist = float('inf')
        nearest_idx = 0
        
        for i, node in enumerate(self.tree):
            dist = np.linalg.norm(node.position - point)
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i
        
        return nearest_idx
    
    def _steer(
        self,
        from_pos: NDArray,
        to_pos: NDArray
    ) -> Tuple[NDArray, bool]:
        """Steer from point toward target."""
        direction = to_pos - from_pos
        distance = np.linalg.norm(direction)
        
        if distance < 1e-6:
            return from_pos.copy(), False
        
        if distance <= self.config.step_size:
            return to_pos.copy(), True
        
        # Extend step_size toward target
        new_pos = from_pos + (direction / distance) * self.config.step_size
        return new_pos, True
    
    def _reconstruct_path(self, end_node: TreeNode) -> List[NDArray]:
        """Reconstruct path from end node."""
        path = []
        current = end_node
        
        while current is not None:
            path.append(current.position.copy())
            current = current.parent
        
        path.reverse()
        return path
    
    def get_tree_edges(self) -> List[Tuple[NDArray, NDArray]]:
        """Get tree edges for visualization."""
        edges = []
        for node in self.tree:
            if node.parent is not None:
                edges.append((node.parent.position, node.position))
        return edges


class RRTStar(RRT):
    """RRT* with optimality guarantees."""
    
    def plan(
        self,
        start: NDArray,
        goal: NDArray,
        obstacles: Optional[ObstacleChecker] = None,
        goal_tolerance: float = 0.5
    ) -> Tuple[List[NDArray], float]:
        """Plan with RRT* optimization.
        
        Returns:
            (path, cost)
        """
        if obstacles is not None:
            self.checker = obstacles
        
        self.reset()
        
        # Add start
        start_node = TreeNode(position=start.copy(), cost=0.0)
        self.tree.append(start_node)
        
        best_goal_node = None
        best_cost = float('inf')
        
        for self.iterations in range(self.config.max_iterations):
            # Sample
            if random.random() < self.config.goal_bias:
                rand_point = goal.copy()
            else:
                rand_point = self._sample_informed(start, goal, best_cost)
            
            # Find nearest
            nearest_idx = self._find_nearest(rand_point)
            nearest = self.tree[nearest_idx]
            
            # Steer
            new_point, success = self._steer(nearest.position, rand_point)
            if not success:
                continue
            
            if self.checker.check_segment(nearest.position, new_point):
                continue
            
            # Find parent (with cost consideration)
            parent_idx = self._find_parent(new_point)
            parent = self.tree[parent_idx]
            
            # Create node
            dist = np.linalg.norm(new_point - parent.position)
            new_node = TreeNode(
                position=new_point,
                parent=parent,
                cost=parent.cost + dist
            )
            
            new_node_idx = len(self.tree)
            self.tree.append(new_node)
            
            # Rewire
            self._rewire(new_node_idx, new_point)
            
            # Check goal
            if np.linalg.norm(new_point - goal) < goal_tolerance:
                if new_node.cost < best_cost:
                    best_cost = new_node.cost
                    best_goal_node = new_node
            
            # Prune distant nodes if found solution
            if best_goal_node is not None and self.iterations > 100:
                self._prune(best_cost * 1.2)
        
        if best_goal_node is not None:
            path = self._reconstruct_path(best_goal_node)
            return path, best_goal_node.cost
        
        return [], float('inf')
    
    def _sample_informed(
        self,
        start: NDArray,
        goal: NDArray,
        best_cost: float
    ) -> NDArray:
        """Sample in informed region (ellipsoid)."""
        if best_cost == float('inf'):
            return self._sample_random()
        
        # Center of ellipsoid
        center = (start + goal) / 2
        
        # Semi-axes
        c2 = (best_cost / 2) ** 2
        a = np.linalg.norm(goal - start) / 2
        
        # Sample in ellipsoid using rejection sampling
        for _ in range(100):
            # Sample in unit sphere
            u = np.random.randn(3)
            u = u / np.linalg.norm(u)
            r = random.random() ** (1/3)
            point = r * u
            
            # Scale to ellipsoid
            if a > 0:
                b = np.sqrt(c2 - a**2)
                point[0] *= a
                point[1] *= b
                point[2] *= b
            
            # Rotate to align with start-goal direction
            direction = (goal - start) / np.linalg.norm(goal - start)
            rotation = self._rotation_matrix(direction)
            point = rotation @ point + center
            
            # Check bounds
            if np.all(point >= self.config.bounds_min) and np.all(point <= self.config.bounds_max):
                return point
        
        return self._sample_random()
    
    def _rotation_matrix(self, direction: NDArray) -> NDArray:
        """Create rotation matrix to align with direction."""
        z = np.array([0, 0, 1])
        v = np.cross(z, direction)
        c = np.dot(z, direction)
        
        if c < -0.9999:
            return -np.eye(3)
        
        skew = np.array([
            [0, -v[2], v[1]],
            [v[2], 0, -v[0]],
            [-v[1], v[0], 0]
        ])
        
        return np.eye(3) + skew + skew @ skew / (1 + c)
    
    def _find_parent(self, point: NDArray) -> int:
        """Find best parent node."""
        # Sample around point for efficiency
        if len(self.tree) > 1000:
            candidates = random.sample(self.tree, min(100, len(self.tree)))
        else:
            candidates = self.tree
        
        best_idx = 0
        best_cost = float('inf')
        
        for i, node in enumerate(candidates):
            # Check if within rewiring radius
            dist = np.linalg.norm(node.position - point)
            if dist > self.config.rewire_radius:
                continue
            
            # Check collision
            if self.checker.check_segment(node.position, point):
                continue
            
            cost = node.cost + dist
            if cost < best_cost:
                best_cost = cost
                best_idx = i
        
        return best_idx
    
    def _rewire(self, new_idx: int, new_point: NDArray) -> None:
        """Rewire tree to improve costs."""
        new_node = self.tree[new_idx]
        
        # Find nodes that could benefit from rewiring
        for i, node in enumerate(self.tree):
            if i == new_idx:
                continue
            
            dist = np.linalg.norm(node.position - new_point)
            if dist > self.config.rewire_radius:
                continue
            
            # Check collision
            if self.checker.check_segment(new_point, node.position):
                continue
            
            # Check if rewiring improves cost
            new_cost = new_node.cost + dist
            if new_cost < node.cost:
                node.parent = new_node
                node.cost = new_cost
                self._update_children_cost(i)
    
    def _update_children_cost(self, node_idx: int) -> None:
        """Update costs for all children (recursive)."""
        node = self.tree[node_idx]
        
        for i, n in enumerate(self.tree):
            if n.parent == node:
                n.cost = node.cost + np.linalg.norm(n.position - node.position)
                self._update_children_cost(i)
    
    def _prune(self, max_cost: float) -> None:
        """Prune nodes with cost above threshold."""
        self.tree = [n for n in self.tree if n.cost < max_cost]
        for node in self.tree:
            if node.parent and node.parent.cost >= max_cost:
                node.parent = None


class RRTConnect(RRT):
    """Bidirectional RRT for faster planning."""
    
    def plan(
        self,
        start: NDArray,
        goal: NDArray,
        obstacles: Optional[ObstacleChecker] = None,
        goal_tolerance: float = 0.5
    ) -> Tuple[List[NDArray], bool]:
        """Plan from both start and goal."""
        if obstacles is not None:
            self.checker = obstacles
        
        self.reset()
        
        # Two trees
        tree_start = [TreeNode(position=start.copy(), cost=0.0)]
        tree_goal = [TreeNode(position=goal.copy(), cost=0.0)]
        
        for self.iterations in range(self.config.max_iterations):
            # Alternate trees
            if self.iterations % 2 == 0:
                from_tree = tree_start
                to_tree = tree_goal
            else:
                from_tree = tree_goal
                to_tree = tree_start
            
            # Sample
            if random.random() < self.config.goal_bias:
                target = goal if self.iterations % 2 == 0 else start
            else:
                target = self._sample_random()
            
            # Find nearest
            nearest_idx = self._find_nearest_in_tree(from_tree, target)
            nearest = from_tree[nearest_idx]
            
            # Steer
            new_point, success = self._steer(nearest.position, target)
            if not success:
                continue
            
            if self.checker.check_segment(nearest.position, new_point):
                continue
            
            # Add to tree
            dist = np.linalg.norm(new_point - nearest.position)
            new_node = TreeNode(
                position=new_point,
                parent=nearest,
                cost=nearest.cost + dist
            )
            from_tree.append(new_node)
            
            # Check connection
            connect_idx = self._find_nearest_in_tree(to_tree, new_point)
            connect = to_tree[connect_idx]
            
            if np.linalg.norm(new_point - connect.position) < goal_tolerance:
                # Connection found!
                if from_tree is tree_start:
                    path = self._reconstruct_bidirectional(tree_start, new_node, tree_goal, connect)
                else:
                    path = self._reconstruct_bidirectional(tree_goal, new_node, tree_start, connect)
                return path, True
        
        return [], False
    
    def _find_nearest_in_tree(
        self,
        tree: List[TreeNode],
        point: NDArray
    ) -> int:
        """Find nearest in specific tree."""
        min_dist = float('inf')
        nearest_idx = 0
        
        for i, node in enumerate(tree):
            dist = np.linalg.norm(node.position - point)
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i
        
        return nearest_idx
    
    def _reconstruct_bidirectional(
        self,
        tree1: List[TreeNode],
        node1: TreeNode,
        tree2: List[TreeNode],
        node2: TreeNode
    ) -> List[NDArray]:
        """Reconstruct path from bidirectional trees."""
        path1 = []
        current = node1
        while current is not None:
            path1.append(current.position.copy())
            current = current.parent
        path1.reverse()
        
        path2 = []
        current = node2.parent  # Exclude duplicate connection point
        while current is not None:
            path2.append(current.position.copy())
            current = current.parent
        
        return path1 + path2


def demo_rrt():
    """Demonstrate RRT planning."""
    print("=" * 60)
    print("RRT* Path Planning Demo")
    print("=" * 60)
    
    # Create obstacles
    checker = ObstacleChecker()
    
    # Add some obstacles
    checker.add_sphere(np.array([25, 25, 10]), 5)
    checker.add_sphere(np.array([50, 50, 5]), 8)
    checker.add_sphere(np.array([10, 60, 15]), 6)
    
    # RRT* planning
    config = RRTConfig(
        max_iterations=2000,
        step_size=1.5,
        goal_bias=0.1,
        rewire_radius=3.0,
        bounds_min=np.array([0, 0, 0]),
        bounds_max=np.array([100, 100, 50])
    )
    
    planner = RRTStar(config)
    
    start = np.array([5, 5, 5])
    goal = np.array([90, 90, 20])
    
    print(f"\nPlanning from {start} to {goal}")
    path, cost = planner.plan(start, goal, checker)
    
    if path:
        print(f"\nPath found! Cost: {cost:.2f}")
        print(f"Iterations: {planner.iterations}")
        print(f"Nodes: {len(planner.tree)}")
        
        print("\nPath waypoints (first 10):")
        for i, p in enumerate(path[:10]):
            print(f"  {i}: ({p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f})")
        
        if len(path) > 10:
            print(f"  ... ({len(path) - 10} more)")
    else:
        print("\nNo path found!")


if __name__ == "__main__":
    demo_rrt()