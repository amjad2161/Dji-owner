"""A* Path Planning for drone navigation.

Implements A* algorithm with:
- 3D occupancy grid
- Diagonal movement support
- Path smoothing
- Dynamic replanning
- Multiple heuristic options

References:
  - Hart, Nilsson, Raphael (1968) - A Formal Basis for Heuristic Search
  - Stentz (1994) - D* Algorithm for Real-Time Planning
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Set, Dict
from collections import defaultdict
import numpy as np
from numpy.typing import NDArray
import heapq


@dataclass
class GridCell:
    """Grid cell for A*."""
    x: int
    y: int
    z: int
    g: float = float('inf')  # Cost from start
    h: float = 0.0          # Heuristic to goal
    f: float = float('inf') # Total cost
    parent: Optional['GridCell'] = None
    
    def __lt__(self, other: 'GridCell') -> bool:
        return self.f < other.f


@dataclass
class AStarConfig:
    """A* configuration."""
    grid_size: float = 1.0       # Grid resolution (m)
    max_height: float = 100.0    # Maximum flight altitude
    heuristic: str = "euclidean"  # "euclidean", "manhattan", "diagonal"
    allow_diagonal: bool = True
    tie_breaker: float = 1.0 + 1e-6  # For consistent ordering


class OccupancyGrid:
    """3D occupancy grid."""
    
    def __init__(self, size: Tuple[int, int, int], resolution: float = 1.0):
        self.size = size  # (nx, ny, nz)
        self.resolution = resolution
        
        # 3D grid: 0 = free, 1 = occupied
        self.grid = np.zeros(size, dtype=np.uint8)
        
        # Origin in world coordinates
        self.origin = np.zeros(3)
    
    def set_origin(self, origin: NDArray) -> None:
        """Set grid origin in world coordinates."""
        self.origin = origin.copy()
    
    def world_to_grid(self, point: NDArray) -> Tuple[int, int, int]:
        """Convert world coordinates to grid indices."""
        idx = ((point - self.origin) / self.resolution).astype(int)
        return tuple(np.clip(idx, [0, 0, 0], np.array(self.size) - 1))
    
    def grid_to_world(self, idx: Tuple[int, int, int]) -> NDArray:
        """Convert grid indices to world coordinates."""
        return self.origin + np.array(idx) * self.resolution
    
    def set_occupied(self, point: NDArray) -> None:
        """Mark cell as occupied."""
        idx = self.world_to_grid(point)
        self.grid[idx] = 1
    
    def set_free(self, point: NDArray) -> None:
        """Mark cell as free."""
        idx = self.world_to_grid(point)
        self.grid[idx] = 0
    
    def is_occupied(self, point: NDArray) -> bool:
        """Check if cell is occupied."""
        idx = self.world_to_grid(point)
        return bool(self.grid[idx[0], idx[1], idx[2]])
    
    def set_box(
        self,
        center: NDArray,
        size: float,
        value: int = 1
    ) -> None:
        """Set box region as occupied/free."""
        half_size = size / 2 / self.resolution
        
        center_idx = self.world_to_grid(center)
        half_idx = np.array([int(half_size)] * 3)
        
        lo = np.clip(center_idx - half_idx, [0, 0, 0], np.array(self.size) - 1)
        hi = np.clip(center_idx + half_idx, [0, 0, 0], np.array(self.size) - 1)
        
        for x in range(lo[0], hi[0] + 1):
            for y in range(lo[1], hi[1] + 1):
                for z in range(lo[2], hi[2] + 1):
                    self.grid[x, y, z] = value
    
    def get_neighbors(
        self,
        idx: Tuple[int, int, int],
        allow_diagonal: bool = True
    ) -> List[Tuple[int, int, int]]:
        """Get valid neighboring cells."""
        nx, ny, nz = self.size
        x, y, z = idx
        
        # 6-connectivity (cardinal directions)
        cardinal = [
            (x+1, y, z), (x-1, y, z),
            (x, y+1, z), (x, y-1, z),
            (x, y, z+1), (x, y, z-1)
        ]
        
        # 12-connectivity (axis-aligned diagonals)
        axis_diag = [
            (x+1, y+1, z), (x+1, y-1, z), (x-1, y+1, z), (x-1, y-1, z),
            (x+1, y, z+1), (x+1, y, z-1), (x-1, y, z+1), (x-1, y, z-1),
            (x, y+1, z+1), (x, y+1, z-1), (x, y-1, z+1), (x, y-1, z-1)
        ]
        
        # 26-connectivity (full diagonals)
        full_diag = [
            (x+1, y+1, z+1), (x+1, y+1, z-1), (x+1, y-1, z+1), (x+1, y-1, z-1),
            (x-1, y+1, z+1), (x-1, y+1, z-1), (x-1, y-1, z+1), (x-1, y-1, z-1)
        ]
        
        neighbors = []
        
        for coords in cardinal:
            if 0 <= coords[0] < nx and 0 <= coords[1] < ny and 0 <= coords[2] < nz:
                neighbors.append(coords)
        
        if allow_diagonal:
            for coords in axis_diag + full_diag:
                if 0 <= coords[0] < nx and 0 <= coords[1] < ny and 0 <= coords[2] < nz:
                    if coords not in neighbors:
                        neighbors.append(coords)
        
        return neighbors
    
    def get_movement_cost(
        self,
        from_idx: Tuple[int, int, int],
        to_idx: Tuple[int, int, int]
    ) -> float:
        """Calculate movement cost between cells."""
        dx = abs(to_idx[0] - from_idx[0])
        dy = abs(to_idx[1] - from_idx[1])
        dz = abs(to_idx[2] - from_idx[2])
        
        # Diagonal movement cost
        if dx + dy + dz == 3:  # Full diagonal
            return self.resolution * 1.732  # sqrt(3)
        elif dx + dy + dz == 2:  # Axis diagonal
            return self.resolution * 1.414  # sqrt(2)
        else:  # Cardinal
            return self.resolution


class AStarPlanner:
    """A* path planner for 3D navigation."""
    
    def __init__(self, config: Optional[AStarConfig] = None):
        self.config = config or AStarConfig()
        self.grid: Optional[OccupancyGrid] = None
        self.goal: Optional[Tuple[int, int, int]] = None
        self.start: Optional[Tuple[int, int, int]] = None
        self.path: List[Tuple[int, int, int]] = []
        
        # Statistics
        self.nodes_expanded = 0
        self.path_length = 0.0
    
    def set_grid(self, grid: OccupancyGrid) -> None:
        """Set occupancy grid."""
        self.grid = grid
    
    def plan(
        self,
        start: NDArray,
        goal: NDArray,
        max_iterations: int = 100000
    ) -> Tuple[List[NDArray], bool]:
        """Plan path from start to goal.
        
        Args:
            start: Start position (3,)
            goal: Goal position (3,)
            max_iterations: Maximum nodes to explore
            
        Returns:
            (path, found): List of waypoints and success status
        """
        if self.grid is None:
            raise ValueError("Grid not set. Call set_grid() first.")
        
        # Convert to grid coordinates
        self.start = self.grid.world_to_grid(start)
        self.goal = self.grid.world_to_grid(goal)
        
        # Check if goal is reachable
        if self.grid.is_occupied(goal):
            print(f"Warning: Goal is occupied: {goal}")
        
        # Initialize open and closed sets
        open_set: List[GridCell] = []
        closed_set: Set[Tuple[int, int, int]] = set()
        
        # Create start cell
        start_cell = GridCell(*self.start)
        start_cell.g = 0
        start_cell.h = self._heuristic(self.start)
        start_cell.f = start_cell.g + start_cell.h
        
        heapq.heappush(open_set, start_cell)
        
        # Goal check counter
        goal_check_interval = 1000
        iterations = 0
        
        while open_set and iterations < max_iterations:
            iterations += 1
            
            # Get cell with lowest f
            current = heapq.heappop(open_set)
            current_idx = (current.x, current.y, current.z)
            
            # Check if goal reached
            if iterations % goal_check_interval == 0:
                if current_idx == self.goal:
                    return self._reconstruct_path(current), True
            
            if current_idx in closed_set:
                continue
            
            closed_set.add(current_idx)
            self.nodes_expanded += 1
            
            # Get neighbors
            neighbors = self.grid.get_neighbors(
                current_idx,
                self.config.allow_diagonal
            )
            
            for neighbor_idx in neighbors:
                if neighbor_idx in closed_set:
                    continue
                
                # Check if occupied
                if self.grid.is_occupied(self.grid.grid_to_world(neighbor_idx)):
                    continue
                
                # Calculate cost
                move_cost = self.grid.get_movement_cost(current_idx, neighbor_idx)
                tentative_g = current.g + move_cost
                
                # Find or create cell
                neighbor_cell = GridCell(*neighbor_idx)
                
                # Check if already in open set with better cost
                in_open = False
                for existing in open_set:
                    if existing.x == neighbor_idx[0] and existing.y == neighbor_idx[1] and existing.z == neighbor_idx[2]:
                        if existing.g <= tentative_g:
                            in_open = True
                            break
                        else:
                            # Update existing
                            existing.g = tentative_g
                            existing.f = tentative_g + existing.h
                            existing.parent = current
                            in_open = True
                            break
                
                if not in_open:
                    neighbor_cell.g = tentative_g
                    neighbor_cell.h = self._heuristic(neighbor_idx)
                    neighbor_cell.f = neighbor_cell.g + neighbor_cell.h
                    neighbor_cell.parent = current
                    heapq.heappush(open_set, neighbor_cell)
        
        # No path found
        return [], False
    
    def _heuristic(self, idx: Tuple[int, int, int]) -> float:
        """Calculate heuristic based on configuration."""
        dx = abs(idx[0] - self.goal[0])
        dy = abs(idx[1] - self.goal[1])
        dz = abs(idx[2] - self.goal[2])
        
        if self.config.heuristic == "manhattan":
            return (dx + dy + dz) * self.grid.resolution
        elif self.config.heuristic == "diagonal":
            # Chebyshev distance
            return max(dx, dy, dz) * self.grid.resolution
        else:  # euclidean
            return np.sqrt(dx**2 + dy**2 + dz**2) * self.grid.resolution
    
    def _reconstruct_path(self, end_cell: GridCell) -> List[NDArray]:
        """Reconstruct path from end cell to start."""
        path = []
        current = end_cell
        
        while current is not None:
            path.append(self.grid.grid_to_world((current.x, current.y, current.z)))
            current = current.parent
        
        path.reverse()
        self.path = path
        self.path_length = sum(
            np.linalg.norm(path[i] - path[i+1])
            for i in range(len(path) - 1)
        )
        
        return path
    
    def smooth(self, method: str = "greedy", factor: float = 0.5) -> List[NDArray]:
        """Smooth path by removing unnecessary waypoints.
        
        Args:
            method: "greedy" or "weighted"
            factor: Smoothing factor (0-1)
            
        Returns:
            Smoothed path
        """
        if len(self.path) < 3:
            return self.path
        
        smoothed = [self.path[0]]
        
        i = 0
        while i < len(self.path) - 1:
            # Try to jump further
            for j in range(len(self.path) - 1, i, -1):
                if self._is_straight_line_safe(self.path[i], self.path[j]):
                    smoothed.append(self.path[j])
                    i = j
                    break
            else:
                i += 1
                if i < len(self.path):
                    smoothed.append(self.path[i])
        
        if smoothed[-1] != self.path[-1]:
            smoothed.append(self.path[-1])
        
        self.path = smoothed
        return smoothed
    
    def _is_straight_line_safe(self, p1: NDArray, p2: NDArray) -> bool:
        """Check if straight line between points is safe."""
        dist = np.linalg.norm(p2 - p1)
        steps = int(dist / (self.grid.resolution * 0.5))
        
        if steps < 2:
            return True
        
        for t in np.linspace(0, 1, steps + 1):
            point = p1 + t * (p2 - p1)
            if self.grid.is_occupied(point):
                return False
        
        return True
    
    def get_path_with_velocity(
        self,
        max_velocity: float
    ) -> List[Tuple[NDArray, float]]:
        """Get path with timing (velocity profile).
        
        Args:
            max_velocity: Maximum velocity along path
            
        Returns:
            List of (position, time)
        """
        if not self.path:
            return []
        
        path_with_time = [(self.path[0], 0.0)]
        
        cumulative_time = 0.0
        for i in range(1, len(self.path)):
            dist = np.linalg.norm(self.path[i] - self.path[i-1])
            segment_time = dist / max_velocity
            cumulative_time += segment_time
            path_with_time.append((self.path[i], cumulative_time))
        
        return path_with_time


class DStarLite:
    """D* Lite algorithm for replanning with changed costs.
    
    Used when environment changes during path execution.
    """
    
    def __init__(self, grid: OccupancyGrid):
        self.grid = grid
        self.km = 0.0
        self.open_list: List = []
        
        # Path storage
        self.path: List[Tuple[int, int, int]] = []
        self.goal: Optional[Tuple[int, int, int]] = None
        self.start: Optional[Tuple[int, int, int]] = None
    
    def initialize(self, start: Tuple, goal: Tuple) -> None:
        """Initialize D* Lite."""
        self.start = start
        self.goal = goal
        self.km = 0.0
        
        # RHS values
        self.rhs = defaultdict(lambda: float('inf'))
        self.g = defaultdict(lambda: float('inf'))
        
        self.rhs[goal] = 0
        heapq.heappush(self.open_list, self._create_key(goal))
    
    def _create_key(self, idx: Tuple) -> Tuple:
        """Create priority key."""
        return (min(self.g[idx], self.rhs[idx]) + self._h(self.start, idx) + self.km, min(self.g[idx], self.rhs[idx]))
    
    def _h(self, idx1: Tuple, idx2: Tuple) -> float:
        """Heuristic."""
        return np.sqrt(sum((a - b) ** 2 for a, b in zip(idx1, idx2)))
    
    def compute_path(self) -> bool:
        """Compute shortest path."""
        while self.open_list and self._is_key_less(
            self.open_list[0],
            self._create_key(self.start)
        ):
            k_old = heapq.heappop(self.open_list)
            k_old_idx = k_old[2] if len(k_old) > 2 else k_old[-1]
            
            if self.g[k_old_idx] > self.rhs[k_old_idx]:
                self.g[k_old_idx] = self.rhs[k_old_idx]
            else:
                self.g[k_old_idx] = float('inf')
                self._update_vertex(k_old_idx)
        
        return self.g[self.start] < float('inf')
    
    def _update_vertex(self, idx: Tuple) -> None:
        """Update vertex and propagate."""
        if idx != self.goal:
            min_rhs = float('inf')
            for pred in self.grid.get_neighbors(idx, allow_diagonal=False):
                cost = self.grid.get_movement_cost(pred, idx) + self.g[pred]
                min_rhs = min(min_rhs, cost)
            self.rhs[idx] = min_rhs
        
        if self.rhs[idx] < float('inf'):
            heapq.heappush(self.open_list, self._create_key(idx))
    
    def _is_key_less(self, k1: Tuple, k2: Tuple) -> bool:
        """Compare keys."""
        return k1[0] < k2[0] or (k1[0] == k2[0] and k1[1] < k2[1])
    
    def update_cost(self, idx: Tuple, new_cost: float) -> None:
        """Update cost of cell."""
        self.grid.set_box(self.grid.grid_to_world(idx), self.grid.resolution, new_cost)
        self._update_vertex(idx)


def demo_astar():
    """Demonstrate A* path planning."""
    print("=" * 60)
    print("A* Path Planning Demo")
    print("=" * 60)
    
    # Create grid
    grid_size = (50, 50, 20)
    resolution = 1.0
    grid = OccupancyGrid(grid_size, resolution)
    
    # Add obstacles
    obstacles = [
        np.array([25, 25, 0]),  # Center building
        np.array([15, 10, 0]),
        np.array([35, 40, 0]),
        np.array([10, 35, 0]),
        np.array([40, 15, 0]),
    ]
    
    for obs in obstacles:
        grid.set_box(obs, size=5, value=1)
    
    # Create planner
    config = AStarConfig(
        grid_size=resolution,
        allow_diagonal=True,
        heuristic="euclidean"
    )
    planner = AStarPlanner(config)
    planner.set_grid(grid)
    
    # Plan path
    start = np.array([0, 0, 0])
    goal = np.array([45, 45, 0])
    
    print(f"\nPlanning path from {start} to {goal}")
    path, found = planner.plan(start, goal)
    
    if found:
        print(f"\nPath found! {len(path)} waypoints")
        print(f"Path length: {planner.path_length:.1f}m")
        print(f"Nodes expanded: {planner.nodes_expanded}")
        
        # Smooth path
        smoothed = planner.smooth()
        print(f"\nSmoothed path: {len(smoothed)} waypoints")
        
        print("\nPath waypoints:")
        for i, p in enumerate(smoothed[:10]):
            print(f"  {i}: ({p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f})")
        if len(smoothed) > 10:
            print(f"  ... ({len(smoothed) - 10} more)")
            print(f"  {len(smoothed)-1}: ({smoothed[-1][0]:.1f}, {smoothed[-1][1]:.1f}, {smoothed[-1][2]:.1f})")
    else:
        print("\nNo path found!")


if __name__ == "__main__":
    demo_astar()