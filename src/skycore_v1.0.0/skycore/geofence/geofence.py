"""Geofencing and safety monitoring for drone operations.

Implements:
- Polygon/cylinder geofences
- No-fly zones (airports, restricted areas)
- Battery-based return-to-home
- Multi-layer safety monitoring
- Emergency protocols
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Callable
import numpy as np
from numpy.typing import NDArray


@dataclass
class GeofenceConfig:
    """Geofence configuration."""
    # Home position
    home_position: NDArray = field(default_factory=lambda: np.zeros(3))
    
    # Battery thresholds
    land_battery_threshold: float = 0.10  # 10% - force landing
    rth_battery_threshold: float = 0.20   # 20% - return to home
    
    # GPS requirements
    min_gps_satellites: int = 8
    min_gps_accuracy: float = 2.0  # meters
    
    # Geofence limits
    max_altitude: float = 120.0   # meters (regulatory limit)
    max_distance: float = 500.0   # meters from home
    
    # Safety margins
    safety_margin: float = 10.0    # meters from boundaries
    
    # Emergency behavior
    emergency_landing: bool = True
    emergency_rth: bool = True


@dataclass
class Geofence:
    """Geofence definition."""
    id: str
    fence_type: str  # "polygon", "cylinder", "sphere"
    
    # Polygon vertices (for polygon type)
    vertices: Optional[List[NDArray]] = None
    
    # Center and radius (for cylinder/sphere)
    center: Optional[NDArray] = None
    radius: float = 0.0
    
    # Altitude range
    min_altitude: float = -float('inf')
    max_altitude: float = float('inf')
    
    # Type: "allow" or "deny"
    permission: str = "allow"
    
    # Color for visualization
    color: Tuple[int, int, int] = (255, 0, 0)


class PolygonGeofence(Geofence):
    """Polygon geofence (2D projection)."""
    
    def __init__(self, vertices: List[NDArray], permission: str = "allow", **kwargs):
        super().__init__(
            id="polygon",
            fence_type="polygon",
            vertices=vertices,
            permission=permission,
            **kwargs
        )
        
        self._compute_bounds()
    
    def _compute_bounds(self) -> None:
        """Pre-compute bounding box."""
        if self.vertices:
            vertices_arr = np.array(self.vertices)
            self.bounds_min = np.min(vertices_arr, axis=0)
            self.bounds_max = np.max(vertices_arr, axis=0)
    
    def contains_point(self, point: NDArray) -> bool:
        """Check if point is inside polygon (ray casting)."""
        if self.vertices is None:
            return False
        
        x, y = point[0], point[1]
        n = len(self.vertices)
        
        inside = False
        j = n - 1
        
        for i in range(n):
            xi, yi = self.vertices[i][0], self.vertices[i][1]
            xj, yj = self.vertices[j][0], self.vertices[j][1]
            
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            
            j = i
        
        return inside
    
    def contains_point_3d(self, point: NDArray) -> bool:
        """Check if point is inside polygon with altitude."""
        if not self.contains_point(point):
            return False
        
        return self.min_altitude <= point[2] <= self.max_altitude
    
    def distance_to_boundary(self, point: NDArray) -> float:
        """Compute distance to nearest boundary."""
        if self.vertices is None:
            return float('inf')
        
        min_dist = float('inf')
        
        for i in range(len(self.vertices)):
            p1 = self.vertices[i]
            p2 = self.vertices[(i + 1) % len(self.vertices)]
            
            # Distance to line segment
            dist = self._point_to_segment_dist(point, p1, p2)
            min_dist = min(min_dist, dist)
        
        return min_dist
    
    @staticmethod
    def _point_to_segment_dist(p: NDArray, a: NDArray, b: NDArray) -> float:
        """Distance from point to line segment."""
        ab = b - a
        ap = p - a
        
        t = np.dot(ap, ab) / np.dot(ab, ab)
        t = np.clip(t, 0, 1)
        
        closest = a + t * ab
        return np.linalg.norm(p - closest)


class CylinderGeofence(Geofence):
    """Cylindrical geofence (horizontal circle with altitude range)."""
    
    def __init__(
        self,
        center: NDArray,
        radius: float,
        permission: str = "allow",
        min_alt: float = -float('inf'),
        max_alt: float = float('inf'),
        **kwargs
    ):
        super().__init__(
            id="cylinder",
            fence_type="cylinder",
            center=center,
            radius=radius,
            permission=permission,
            min_altitude=min_alt,
            max_altitude=max_alt,
            **kwargs
        )
    
    def contains_point(self, point: NDArray) -> bool:
        """Check if point is inside cylinder."""
        # Horizontal distance check
        horizontal = np.sqrt((point[0] - self.center[0])**2 + (point[1] - self.center[1])**2)
        
        if horizontal > self.radius:
            return False
        
        # Altitude check
        if point[2] < self.min_altitude or point[2] > self.max_altitude:
            return False
        
        return True
    
    def contains_point_3d(self, point: NDArray) -> bool:
        """Check if point is inside (uses same as contains_point)."""
        return self.contains_point(point)
    
    def distance_to_boundary(self, point: NDArray) -> float:
        """Distance to cylinder boundary."""
        horizontal = np.sqrt(
            (point[0] - self.center[0])**2 + (point[1] - self.center[1])**2
        )
        return self.radius - horizontal


class GeofenceManager:
    """Manages geofences and monitors compliance."""
    
    def __init__(self, config: Optional[GeofenceConfig] = None):
        self.config = config or GeofenceConfig()
        self.fences: List[Geofence] = []
        
        # No-fly zones (always checked first)
        self.no_fly_zones: List[Geofence] = []
        
        # State
        self.violation_active = False
        self.violation_type: Optional[str] = None
        self.violation_severity: float = 0.0
    
    def add_fence(self, fence: Geofence) -> None:
        """Add geofence."""
        if fence.permission == "deny":
            self.no_fly_zones.append(fence)
        else:
            self.fences.append(fence)
    
    def remove_fence(self, fence_id: str) -> bool:
        """Remove geofence by ID."""
        for fence in self.fences + self.no_fly_zones:
            if fence.id == fence_id:
                self.fences.remove(fence)
                self.no_fly_zones.remove(fence)
                return True
        return False
    
    def clear_fences(self) -> None:
        """Remove all geofences."""
        self.fences = []
        self.no_fly_zones = []
    
    def check_position(
        self,
        position: NDArray,
        velocity: Optional[NDArray] = None
    ) -> Tuple[bool, Optional[str], float]:
        """Check if position violates any geofence.
        
        Returns:
            (is_safe, violation_type, severity)
        """
        severity = 0.0
        
        # Check no-fly zones first (critical)
        for zone in self.no_fly_zones:
            if zone.contains_point_3d(position):
                return False, "no_fly_zone", 1.0
        
        # Check altitude
        if position[2] > self.config.max_altitude:
            severity = max(severity, 0.5)
        
        # Check distance from home
        home = self.config.home_position
        distance = np.linalg.norm(position - home)
        
        if distance > self.config.max_distance:
            severity = max(severity, 0.7)
        
        # Check geofences
        for fence in self.fences:
            if fence.contains_point_3d(position):
                # Inside allowed zone - OK
                continue
            
            # Outside - check distance to boundary
            dist = fence.distance_to_boundary(position)
            
            if dist < 0:
                severity = max(severity, 0.3)
            elif dist < self.config.safety_margin:
                severity = max(severity, 0.1)
        
        # Velocity-based prediction
        if velocity is not None and severity > 0:
            # Predict future position
            t_lookahead = 1.0  # 1 second lookahead
            future_pos = position + velocity * t_lookahead
            
            for zone in self.no_fly_zones:
                if zone.contains_point_3d(future_pos):
                    severity = max(severity, 0.8)
                    break
        
        self.violation_active = severity > 0
        self.violation_severity = severity
        
        return severity == 0, self.violation_type, severity
    
    def get_safe_position(
        self,
        position: NDArray,
        preferred_direction: Optional[NDArray] = None
    ) -> NDArray:
        """Get nearest safe position."""
        safe_pos = position.copy()
        
        # Clamp altitude
        safe_pos[2] = min(safe_pos[2], self.config.max_altitude)
        
        # Clamp distance from home
        home = self.config.home_position
        distance = np.linalg.norm(safe_pos - home)
        
        if distance > self.config.max_distance:
            direction = (safe_pos - home) / distance
            safe_pos = home + direction * self.config.max_distance
        
        # Push out of no-fly zones
        for zone in self.no_fly_zones:
            if zone.contains_point_3d(safe_pos):
                # Find direction to push out
                if zone.fence_type == "cylinder" and zone.center is not None:
                    direction = safe_pos - zone.center
                    direction[2] = 0  # Keep altitude change
                    dir_norm = np.linalg.norm(direction)
                    if dir_norm > 0:
                        direction = direction / dir_norm
                        safe_pos = zone.center + direction * (zone.radius + 1)
        
        return safe_pos
    
    def get_emergency_action(
        self,
        position: NDArray,
        battery_level: float,
        gps_quality: Tuple[int, float]
    ) -> str:
        """Determine emergency action based on conditions.
        
        Args:
            position: Current position
            battery_level: Battery remaining (0-1)
            gps_quality: (num_satellites, hdop)
            
        Returns:
            Action: "none", "hover", "rth", "land", "emergency_land"
        """
        satellites, accuracy = gps_quality
        
        # Critical: low battery
        if battery_level <= self.config.land_battery_threshold:
            return "emergency_land"
        
        # Low battery with distance from home
        if battery_level <= self.config.rth_battery_threshold:
            home_distance = np.linalg.norm(position - self.config.home_position)
            if home_distance > 100:  # Far from home
                return "rth"
        
        # GPS issues
        if satellites < self.config.min_gps_satellites:
            return "hover"  # Hover and wait for GPS
        
        if accuracy > self.config.min_gps_accuracy * 3:
            return "hover"
        
        # Out of geofence
        is_safe, _, severity = self.check_position(position)
        if not is_safe and severity > 0.5:
            return "rth"
        
        return "none"
    
    def check_fence_intersection(
        self,
        p1: NDArray,
        p2: NDArray
    ) -> List[Tuple[NDArray, Geofence]]:
        """Check if line segment intersects any geofence.
        
        Returns:
            List of (intersection_point, fence) pairs
        """
        intersections = []
        
        for fence in self.no_fly_zones:
            if fence.fence_type == "cylinder" and fence.center is not None:
                # Check cylinder intersection
                hit = self._line_cylinder_intersection(p1, p2, fence)
                if hit is not None:
                    intersections.append((hit, fence))
            
            elif fence.fence_type == "polygon" and fence.vertices:
                # Check each edge
                for i in range(len(fence.vertices)):
                    v1 = fence.vertices[i]
                    v2 = fence.vertices[(i + 1) % len(fence.vertices)]
                    
                    hit = self._line_line_intersection_3d(p1, p2, v1, v2)
                    if hit is not None:
                        intersections.append((hit, fence))
                        break
        
        return intersections
    
    @staticmethod
    def _line_cylinder_intersection(
        p1: NDArray,
        p2: NDArray,
        cylinder: CylinderGeofence
    ) -> Optional[NDArray]:
        """Check line-cylinder intersection."""
        # Simplified: check if either endpoint is inside
        if cylinder.contains_point(p1) or cylinder.contains_point(p2):
            # Find intersection point
            direction = p2 - p1
            center = cylinder.center
            
            # Project to 2D (ignore altitude)
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            cx = p1[0] - center[0]
            cy = p1[1] - center[1]
            
            a = dx * dx + dy * dy
            b = 2 * (cx * dx + cy * dy)
            c = cx * cx + cy * cy - cylinder.radius ** 2
            
            discriminant = b * b - 4 * a * c
            
            if discriminant >= 0:
                t1 = (-b - np.sqrt(discriminant)) / (2 * a)
                t2 = (-b + np.sqrt(discriminant)) / (2 * a)
                
                if 0 <= t1 <= 1:
                    return p1 + t1 * (p2 - p1)
                if 0 <= t2 <= 1:
                    return p1 + t2 * (p2 - p1)
        
        return None
    
    @staticmethod
    def _line_line_intersection_3d(
        p1: NDArray,
        p2: NDArray,
        v1: NDArray,
        v2: NDArray
    ) -> Optional[NDArray]:
        """Check line-line intersection in 3D (simplified)."""
        # Just check endpoints for simplicity
        if (np.linalg.norm(p1 - v1) < 0.1 or np.linalg.norm(p1 - v2) < 0.1 or
            np.linalg.norm(p2 - v1) < 0.1 or np.linalg.norm(p2 - v2) < 0.1):
            return (p1 + p2) / 2
        return None


def demo_geofence():
    """Demonstrate geofence management."""
    print("=" * 60)
    print("Geofence Manager Demo")
    print("=" * 60)
    
    # Create geofence manager
    config = GeofenceConfig(
        home_position=np.array([0, 0, 0]),
        max_altitude=100,
        max_distance=500
    )
    manager = GeofenceManager(config)
    
    # Add no-fly zone (airport)
    airport = CylinderGeofence(
        center=np.array([200, 200, 0]),
        radius=100,
        permission="deny",
        color=(255, 0, 0)
    )
    manager.add_fence(airport)
    
    # Add operational zone
    operational = PolygonGeofence(
        vertices=[
            np.array([0, 0, 0]),
            np.array([100, 0, 0]),
            np.array([100, 100, 0]),
            np.array([0, 100, 0])
        ],
        permission="allow"
    )
    manager.add_fence(operational)
    
    # Test positions
    test_positions = [
        np.array([50, 50, 20]),    # Inside operational zone
        np.array([150, 150, 20]), # Near airport
        np.array([200, 200, 20]), # Inside airport (should fail)
        np.array([50, 50, 150]),  # Too high
        np.array([400, 400, 20]), # Far from home
    ]
    
    print("\nPosition checks:")
    for pos in test_positions:
        safe, violation, severity = manager.check_position(pos)
        status = "SAFE" if safe else f"VIOLATION: {violation}"
        print(f"  {pos} -> {status} (severity: {severity:.2f})")
    
    # Test emergency actions
    print("\nEmergency action tests:")
    battery_levels = [0.05, 0.15, 0.30]
    for battery in battery_levels:
        action = manager.get_emergency_action(
            np.array([50, 50, 20]),
            battery,
            (10, 1.0)
        )
        print(f"  Battery {battery*100:.0f}%: {action}")
    
    # Get safe position
    print("\nSafe position computation:")
    unsafe_pos = np.array([250, 250, 50])
    safe_pos = manager.get_safe_position(unsafe_pos)
    print(f"  Unsafe: {unsafe_pos} -> Safe: {safe_pos}")


if __name__ == "__main__":
    demo_geofence()