"""
SkyCore A* Path Planner
=======================
Optimal path planning using A* algorithm.
"""

import numpy as np
from typing import List, Tuple, Dict, Optional, Set
import heapq
import logging

log = logging.getLogger(__name__)


class Node:
    """A* node."""
    def __init__(self, x: int, y: int, z: int, g: float = 0, h: float = 0,
                 parent: Optional['Node'] = None):
        self.x = x
        self.y = y
        self.z = z
        self.g = g  # Cost from start
        self.h = h  # Heuristic to goal
        self.f = g + h  # Total cost
        self.parent = parent
    
    def __lt__(self, other):
        return self.f < other.f
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y and self.z == other.z
    
    def __hash__(self):
        return hash((self.x, self.y, self.z))


class AStarPlanner:
    """
    A* Path Planner for drone navigation.
    
    Features:
    - 3D grid-based planning
    - Obstacle avoidance
    - Diagonal movement
    - Path smoothing
    """
    
    def __init__(self, grid_size: float = 1.0, max_altitude: float = 120):
        """
        Initialize A* planner.
        
        Args:
            grid_size: Grid cell size (meters)
            max_altitude: Maximum allowed altitude (meters)
        """
        self.grid_size = grid_size
        self.max_altitude = max_altitude
        
        # 3D occupancy grid
        self.occupancy = None
        self.grid_shape = None
        
        # 26-connected neighbors (3D diagonal)
        self.neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    self.neighbors.append((dx, dy, dz))
    
    def set_occupancy_grid(self, occupancy: np.ndarray):
        """
        Set 3D occupancy grid.
        
        Args:
            occupancy: 3D boolean array (True = obstacle)
        """
        self.occupancy = occupancy
        self.grid_shape = occupancy.shape
    
    def plan(self, start: Tuple[float, float, float],
             goal: Tuple[float, float, float],
             obstacles: Optional[List[Tuple[float, float, float, float]]] = None,
             safe_radius: float = 5.0) -> List[Tuple[float, float, float]]:
        """
        Plan path from start to goal.
        
        Args:
            start: Start position (lat, lon, alt)
            goal: Goal position (lat, lon, alt)
            obstacles: List of (cx, cy, cz, radius) spherical obstacles
            safe_radius: Safety radius around obstacles
            
        Returns:
            List of waypoints [(lat, lon, alt), ...]
        """
        # Convert to grid coordinates
        start_grid = self._world_to_grid(start)
        goal_grid = self._world_to_grid(goal)
        
        # Check bounds
        if not self._in_bounds(start_grid) or not self._in_bounds(goal_grid):
            log.warning("Start or goal out of bounds")
            return [start, goal]
        
        # Check if goal is accessible
        if self._is_obstacle(goal_grid):
            log.warning("Goal position is an obstacle")
            # Find nearest free cell
            goal_grid = self._find_nearest_free(goal_grid)
        
        # A* search
        open_set = []
        closed_set = set()
        node_map = {}
        
        start_node = Node(start_grid[0], start_grid[1], start_grid[2], 
                         g=0, h=self._heuristic(start_grid, goal_grid))
        
        heapq.heappush(open_set, start_node)
        node_map[start_grid] = start_node
        
        iterations = 0
        max_iterations = 100000
        
        while open_set and iterations < max_iterations:
            iterations += 1
            
            # Get node with lowest f
            current = heapq.heappop(open_set)
            
            # Check if reached goal
            if current == Node(goal_grid[0], goal_grid[1], goal_grid[2]):
                return self._reconstruct_path(current, start)
            
            closed_key = (current.x, current.y, current.z)
            if closed_key in closed_set:
                continue
            closed_set.add(closed_key)
            
            # Check neighbors
            for dx, dy, dz in self.neighbors:
                nx, ny, nz = current.x + dx, current.y + dy, current.z + dz
                
                # Skip if out of bounds
                if not self._in_bounds((nx, ny, nz)):
                    continue
                
                # Skip if obstacle
                if self._is_obstacle((nx, ny, nz)):
                    continue
                
                # Skip if in closed set
                if (nx, ny, nz) in closed_set:
                    continue
                
                # Movement cost (more for diagonal)
                move_cost = np.sqrt(dx**2 + dy**2 + dz**2) * self.grid_size
                
                # Check obstacles
                if self._collides_with_obstacle((nx, ny, nz), obstacles, safe_radius):
                    continue
                
                g = current.g + move_cost
                h = self._heuristic((nx, ny, nz), goal_grid)
                
                neighbor = Node(nx, ny, nz, g, h, current)
                
                # Check if better path exists
                neighbor_key = (nx, ny, nz)
                if neighbor_key in node_map:
                    existing = node_map[neighbor_key]
                    if existing.g <= g:
                        continue
                
                node_map[neighbor_key] = neighbor
                heapq.heappush(open_set, neighbor)
        
        log.warning(f"A* search failed after {iterations} iterations")
        return [start, goal]  # Return direct path if failed
    
    def _world_to_grid(self, pos: Tuple[float, float, float]) -> Tuple[int, int, int]:
        """Convert world coordinates to grid."""
        # Assuming position is in degrees and meters
        return (
            int(pos[0] / self.grid_size),
            int(pos[1] / self.grid_size),
            int(pos[2] / self.grid_size)
        )
    
    def _grid_to_world(self, grid: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """Convert grid to world coordinates."""
        return (
            grid[0] * self.grid_size,
            grid[1] * self.grid_size,
            grid[2] * self.grid_size
        )
    
    def _in_bounds(self, grid: Tuple[int, int, int]) -> bool:
        """Check if grid position is within bounds."""
        if self.grid_shape is None:
            return True
        return (0 <= grid[0] < self.grid_shape[0] and
                0 <= grid[1] < self.grid_shape[1] and
                0 <= grid[2] < self.grid_shape[2])
    
    def _is_obstacle(self, grid: Tuple[int, int, int]) -> bool:
        """Check if grid cell is obstacle."""
        if self.occupancy is None:
            return False
        try:
            return self.occupancy[grid[0], grid[1], grid[2]]
        except IndexError:
            return True
    
    def _heuristic(self, a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
        """Euclidean distance heuristic."""
        return np.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) * self.grid_size
    
    def _collides_with_obstacle(self, pos: Tuple[int, int, int],
                               obstacles: List, safe_radius: float) -> bool:
        """Check collision with spherical obstacles."""
        if obstacles is None:
            return False
        
        pos_world = self._grid_to_world(pos)
        
        for cx, cy, cz, radius in obstacles:
            dist = np.sqrt((pos_world[0]-cx)**2 + 
                          (pos_world[1]-cy)**2 + 
                          (pos_world[2]-cz)**2)
            if dist < radius + safe_radius:
                return True
        
        return False
    
    def _find_nearest_free(self, grid: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """Find nearest free cell to given position."""
        if not self._is_obstacle(grid):
            return grid
        
        # BFS search
        visited = {grid}
        queue = [grid]
        
        while queue:
            current = queue.pop(0)
            if not self._is_obstacle(current):
                return current
            
            for dx, dy, dz in self.neighbors:
                nx, ny, nz = current[0]+dx, current[1]+dy, current[2]+dz
                neighbor = (nx, ny, nz)
                
                if neighbor not in visited and self._in_bounds(neighbor):
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        return grid
    
    def _reconstruct_path(self, node: Node, start: Tuple[float, float, float]) -> List:
        """Reconstruct path from goal to start."""
        path = []
        current = node
        
        while current is not None:
            grid = (current.x, current.y, current.z)
            world = self._grid_to_world(grid)
            path.append((world[0] + start[0], 
                        world[1] + start[1],
                        world[2] + start[2]))
            current = current.parent
        
        path.reverse()
        
        # Smooth path
        smoothed = self._smooth_path(path)
        
        return smoothed
    
    def _smooth_path(self, path: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        """Remove unnecessary waypoints from path."""
        if len(path) <= 2:
            return path
        
        smoothed = [path[0]]
        
        for i in range(1, len(path) - 1):
            # Check if point is needed
            prev = smoothed[-1]
            next_pt = path[i + 1]
            
            # Check if prev->next is direct line of sight
            if not self._line_of_sight(prev, next_pt):
                smoothed.append(path[i])
        
        smoothed.append(path[-1])
        
        return smoothed
    
    def _line_of_sight(self, start: Tuple[float, float, float],
                       end: Tuple[float, float, float]) -> bool:
        """Check if direct line between points is clear."""
        # Sample points along line
        dist = np.sqrt((end[0]-start[0])**2 + (end[1]-start[1])**2 + (end[2]-start[2])**2)
        n_samples = max(int(dist / (self.grid_size / 2)), 2)
        
        for i in range(n_samples):
            t = i / (n_samples - 1)
            x = start[0] + t * (end[0] - start[0])
            y = start[1] + t * (end[1] - start[1])
            z = start[2] + t * (end[2] - start[2])
            
            grid = self._world_to_grid((x, y, z))
            if self._is_obstacle(grid):
                return False
        
        return True