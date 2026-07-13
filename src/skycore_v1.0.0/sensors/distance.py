"""Distance sensors (LIDAR, ultrasonic, ToF) for obstacle detection.

Implements:
- LIDAR point cloud processing
- Ultrasonic ranging
- Time-of-Flight (ToF) sensors
- Obstacle map generation
- Sensor fusion for depth estimation
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
import numpy as np
from numpy.typing import NDArray
import time
import math


@dataclass
class DistanceSensorConfig:
    """Distance sensor configuration."""
    sensor_type: str = "tof"  # "lidar", "ultrasonic", "tof"
    
    # Range parameters
    min_range: float = 0.05    # m
    max_range: float = 12.0    # m
    field_of_view: float = 0.5  # radians (half-angle for single beam)
    
    # Accuracy
    range_accuracy: float = 0.03  # m
    angular_accuracy: float = 1.0  # degrees
    
    # Update rate
    update_rate: float = 20.0  # Hz
    
    # Noise parameters
    noise_std: float = 0.02   # m
    
    # Physical parameters
    mounting_position: NDArray = field(default_factory=lambda: np.zeros(3))
    mounting_orientation: NDArray = field(default_factory=lambda: np.array([0, 0, 0]))  # Euler angles


@dataclass
class RangeMeasurement:
    """Single range measurement."""
    timestamp: float
    range: float              # meters
    azimuth: float           # radians
    elevation: float         # radians
    
    # Confidence
    signal_strength: float = 1.0  # 0-1
    quality: float = 1.0     # 0-1
    
    # Raw data
    raw_intensity: float = 0


class LIDARSensor:
    """LIDAR sensor model and processing."""
    
    def __init__(self, config: Optional[DistanceSensorConfig] = None):
        self.config = config or DistanceSensorConfig()
        
        # Scan data
        self.scan_points: List[RangeMeasurement] = []
        self.last_scan_time = 0.0
        
        # Configuration
        self.scan_rate = 20.0  # Hz
        self.points_per_scan = 360
        
        # Point cloud buffer
        self.point_cloud: List[NDArray] = []
        self.max_cloud_size = 10000
    
    def simulate_scan(
        self,
        timestamp: float,
        obstacles: List[Tuple[NDArray, float]]
    ) -> List[RangeMeasurement]:
        """Simulate LIDAR scan with obstacles.
        
        Args:
            timestamp: Current timestamp
            obstacles: List of (position, radius) for obstacles
            
        Returns:
            List of range measurements
        """
        measurements = []
        
        # Simulate 360 beams (1 degree resolution)
        for angle_idx in range(self.points_per_scan):
            azimuth = 2 * math.pi * angle_idx / self.points_per_scan
            
            # Find nearest obstacle in this direction
            min_range = self.config.max_range
            
            for obs_pos, obs_radius in obstacles:
                # Check intersection with circular obstacle
                # Simplified: ray-sphere intersection
                hit_range = self._ray_sphere_intersection(
                    np.zeros(3),  # Origin (in sensor frame)
                    np.array([math.cos(azimuth), math.sin(azimuth), 0]),
                    obs_pos,
                    obs_radius
                )
                
                if hit_range is not None and min(self.config.min_range, self.config.max_range):
                    min_range = min(min_range, hit_range)
            
            # Add noise
            if min_range < self.config.max_range:
                noise = np.random.randn() * self.config.noise_std
                range_measured = max(self.config.min_range, min_range + noise)
            else:
                range_measured = self.config.max_range
            
            measurement = RangeMeasurement(
                timestamp=timestamp,
                range=range_measured,
                azimuth=azimuth,
                elevation=0,
                quality=1.0 if range_measured < self.config.max_range else 0.0
            )
            
            measurements.append(measurement)
        
        self.scan_points = measurements
        self.last_scan_time = timestamp
        
        return measurements
    
    @staticmethod
    def _ray_sphere_intersection(
        ray_origin: NDArray,
        ray_direction: NDArray,
        sphere_center: NDArray,
        sphere_radius: float
    ) -> Optional[float]:
        """Compute ray-sphere intersection."""
        oc = ray_origin - sphere_center
        
        a = np.dot(ray_direction, ray_direction)
        b = 2.0 * np.dot(oc, ray_direction)
        c = np.dot(oc, oc) - sphere_radius ** 2
        
        discriminant = b * b - 4 * a * c
        
        if discriminant < 0:
            return None
        
        t = (-b - math.sqrt(discriminant)) / (2 * a)
        
        if t > 0:
            return t
        return None
    
    def get_point_cloud(self) -> NDArray:
        """Get current point cloud in sensor frame.
        
        Returns:
            Nx3 array of points (x, y, z)
        """
        points = []
        
        for measurement in self.scan_points:
            if measurement.quality > 0.5:
                x = measurement.range * math.cos(measurement.azimuth) * math.cos(measurement.elevation)
                y = measurement.range * math.sin(measurement.azimuth) * math.cos(measurement.elevation)
                z = measurement.range * math.sin(measurement.elevation)
                points.append([x, y, z])
        
        return np.array(points) if points else np.zeros((0, 3))
    
    def compute_obstacle_distance(self, direction: NDArray, obstacles: List[NDArray]) -> float:
        """Compute distance to nearest obstacle in given direction.
        
        Args:
            direction: Unit vector in world frame
            obstacles: List of obstacle positions
            
        Returns:
            Distance to nearest obstacle, or max_range if none
        """
        min_dist = self.config.max_range
        
        for obs_pos in obstacles:
            # Distance to obstacle center
            dist = np.linalg.norm(obs_pos)
            
            # Check if in field of view
            if dist > 0:
                obs_dir = obs_pos / dist
                angle = math.acos(np.clip(np.dot(direction, obs_dir), -1, 1))
                
                if angle < self.config.field_of_view and dist < min_dist:
                    min_dist = dist
        
        return min_dist
    
    def detect_edges(self, threshold: float = 0.3) -> List[float]:
        """Detect edges in scan (potential obstacle boundaries).
        
        Args:
            threshold: Jump threshold in meters
            
        Returns:
            List of azimuth angles where edges detected
        """
        if len(self.scan_points) < 3:
            return []
        
        edges = []
        
        for i in range(len(self.scan_points) - 1):
            range_diff = abs(self.scan_points[i + 1].range - self.scan_points[i].range)
            
            # Account for wrap-around at 0/360
            range_diff2 = abs(
                self.scan_points[0].range - self.scan_points[-1].range
            )
            
            if range_diff > threshold:
                edges.append(self.scan_points[i].azimuth)
        
        return edges


class UltrasonicSensor:
    """Ultrasonic distance sensor."""
    
    SPEED_OF_SOUND = 343.0  # m/s at 20°C
    
    def __init__(self, config: Optional[DistanceSensorConfig] = None):
        self.config = config or DistanceSensorConfig()
        
        # Override for ultrasonic characteristics
        self.config.max_range = 4.0  # Typical max range
        self.config.noise_std = 0.02
        
        # Temperature compensation
        self.temperature = 20.0  # Celsius
    
    def measure(self, distance: float, temperature: float = 20.0) -> float:
        """Simulate ultrasonic measurement.
        
        Args:
            distance: True distance in meters
            temperature: Air temperature in Celsius
            
        Returns:
            Measured distance
        """
        self.temperature = temperature
        
        # Time of flight (round trip)
        speed_of_sound = 331.3 + 0.606 * temperature  # m/s
        time_of_flight = 2 * distance / speed_of_sound
        
        # Add noise
        noise_std = self.config.noise_std * (1 + distance / self.config.max_range)
        noise = np.random.randn() * noise_std
        
        measured_distance = distance + noise
        
        # Clamp to valid range
        return np.clip(measured_distance, self.config.min_range, self.config.max_range)
    
    def check_valid_measurement(self, measured_distance: float) -> bool:
        """Check if measurement is valid."""
        if measured_distance < self.config.min_range * 0.9:
            return False
        if measured_distance > self.config.max_range * 0.95:
            return False
        return True


class ToFSensor:
    """Time-of-Flight camera sensor."""
    
    def __init__(self, config: Optional[DistanceSensorConfig] = None):
        self.config = config or DistanceSensorConfig()
        
        # ToF-specific parameters
        self.resolution_h = 240  # Horizontal resolution
        self.resolution_v = 176  # Vertical resolution
        self.horizontal_fov = 1.0  # radians
        self.vertical_fov = 0.75   # radians
    
    def generate_depth_image(
        self,
        distance_map: NDArray
    ) -> NDArray:
        """Generate simulated depth image.
        
        Args:
            distance_map: 2D array of distances (meters)
            
        Returns:
            Depth image in meters
        """
        h, w = self.resolution_h, self.resolution_v
        
        if distance_map.shape != (h, w):
            # Resize input
            from scipy.ndimage import zoom
            scale = (h / distance_map.shape[0], w / distance_map.shape[1])
            distance_map = zoom(distance_map, scale, order=1)
        
        # Add noise
        noise = np.random.randn(h, w) * self.config.noise_std
        depth_image = distance_map + noise
        
        return np.clip(depth_image, self.config.min_range, self.config.max_range)
    
    def depth_to_point_cloud(
        self,
        depth_image: NDArray
    ) -> NDArray:
        """Convert depth image to point cloud.
        
        Args:
            depth_image: HxW depth image
            
        Returns:
            Nx3 point cloud (flattened)
        """
        h, w = depth_image.shape
        
        # Generate pixel coordinates
        u = np.arange(w) - w / 2
        v = np.arange(h) - h / 2
        
        # Normalize to angles
        u_norm = u / w * self.horizontal_fov
        v_norm = v / h * self.vertical_fov
        
        # Create meshgrid
        U, V = np.meshgrid(u_norm, v_norm)
        D = depth_image
        
        # Convert to 3D points (camera frame)
        x = D * np.sin(U)
        y = D * np.cos(U) * np.sin(V)
        z = -D * np.cos(U) * np.cos(V)
        
        # Stack and flatten
        points = np.stack([x.flatten(), y.flatten(), z.flatten()], axis=1)
        
        # Remove invalid points
        valid = (D.flatten() > self.config.min_range) & (D.flatten() < self.config.max_range)
        
        return points[valid]


class ObstacleMap:
    """2D/3D obstacle map for collision avoidance."""
    
    def __init__(self, resolution: float = 0.1, size: Tuple[int, int, int] = (100, 100, 20)):
        self.resolution = resolution
        self.size = size
        
        # Occupancy grid
        self.occupancy = np.zeros(size, dtype=np.float32)
        
        # Probability thresholds
        self.prob_occ = 0.7
        self.prob_free = 0.3
        
        # Update counters
        self.update_count = 0
    
    def update_from_scan(
        self,
        measurements: List[RangeMeasurement],
        sensor_position: NDArray,
        sensor_orientation: NDArray
    ) -> None:
        """Update occupancy grid from LIDAR scan.
        
        Args:
            measurements: List of range measurements
            sensor_position: Sensor position in world frame
            sensor_orientation: Sensor orientation (quaternion)
        """
        self.update_count += 1
        
        # Rotation matrix from orientation
        R = self._quaternion_to_rotation(sensor_orientation)
        
        for measurement in measurements:
            if measurement.quality < 0.5:
                continue
            
            # Transform measurement to world frame
            # Local coordinates
            local_x = measurement.range * math.cos(measurement.azimuth) * math.cos(measurement.elevation)
            local_y = measurement.range * math.sin(measurement.azimuth) * math.cos(measurement.elevation)
            local_z = measurement.range * math.sin(measurement.elevation)
            
            local_point = np.array([local_x, local_y, local_z])
            world_point = R @ local_point + sensor_position
            
            # Update grid along ray
            self._update_ray(sensor_position, world_point, measurement.range)
    
    def _update_ray(
        self,
        start: NDArray,
        end: NDArray,
        max_range: float
    ) -> None:
        """Update grid cells along ray."""
        # Ray marching
        direction = end - start
        distance = np.linalg.norm(direction)
        
        if distance < 0.01:
            return
        
        direction = direction / distance
        
        # Number of steps
        n_steps = int(distance / (self.resolution * 0.5))
        
        for i in range(n_steps):
            t = i / n_steps
            point = start + t * direction
            
            idx = self._world_to_idx(point)
            
            if idx is None:
                continue
            
            # Update probability
            if i == n_steps - 1:
                # Last point - occupied
                self.occupancy[idx] = self.occupancy[idx] * 0.7 + 0.3
            else:
                # Free space
                self.occupancy[idx] = self.occupancy[idx] * 0.8 + 0.2
    
    def _world_to_idx(self, point: NDArray) -> Optional[Tuple[int, int, int]]:
        """Convert world coordinates to grid index."""
        idx = (point / self.resolution).astype(int)
        
        if (idx >= 0).all() and (idx < np.array(self.size)).all():
            return tuple(idx)
        
        return None
    
    @staticmethod
    def _quaternion_to_rotation(q: NDArray) -> NDArray:
        """Convert quaternion to rotation matrix."""
        w, x, y, z = q
        
        return np.array([
            [1 - 2*(y**2 + z**2), 2*(x*y - w*z), 2*(x*z + w*y)],
            [2*(x*y + w*z), 1 - 2*(x**2 + z**2), 2*(y*z - w*x)],
            [2*(x*z - w*y), 2*(y*z + w*x), 1 - 2*(x**2 + y**2)]
        ])
    
    def check_collision(self, position: NDArray, radius: float = 0.3) -> Tuple[bool, float]:
        """Check if position collides with obstacles.
        
        Args:
            position: Position to check
            radius: Collision radius
            
        Returns:
            (collision, distance_to_nearest)
        """
        # Check cells in radius
        d = int(radius / self.resolution)
        
        idx = (position / self.resolution).astype(int)
        
        min_prob = 0.0
        
        for dx in range(-d, d + 1):
            for dy in range(-d, d + 1):
                for dz in range(-d, d + 1):
                    check_idx = idx + np.array([dx, dy, dz])
                    
                    if (check_idx >= 0).all() and (check_idx < np.array(self.size)).all():
                        prob = self.occupancy[tuple(check_idx)]
                        min_prob = max(min_prob, prob)
        
        collision = min_prob > self.prob_occ
        distance = (1 - min_prob) * radius / 0.5  # Approximate distance
        
        return collision, distance
    
    def get_nearest_obstacle_direction(
        self,
        position: NDArray,
        directions: List[NDArray]
    ) -> Tuple[NDArray, float]:
        """Find nearest obstacle direction.
        
        Args:
            position: Current position
            directions: List of direction vectors to check
            
        Returns:
            (nearest_direction, distance)
        """
        min_dist = float('inf')
        nearest_dir = None
        
        for direction in directions:
            dist = self._raycast(position, direction)
            
            if dist < min_dist:
                min_dist = dist
                nearest_dir = direction
        
        return nearest_dir if nearest_dir is not None else np.zeros(3), min_dist
    
    def _raycast(self, start: NDArray, direction: NDArray) -> float:
        """Raycast to find distance to obstacle."""
        direction = direction / np.linalg.norm(direction)
        
        for t in np.arange(0, 10, self.resolution):
            point = start + t * direction
            idx = self._world_to_idx(point)
            
            if idx is not None and self.occupancy[idx] > self.prob_occ:
                return t
        
        return 10.0  # Max range


def demo_distance_sensors():
    """Demonstrate distance sensor processing."""
    print("=" * 60)
    print("Distance Sensors Demo")
    print("=" * 60)
    
    # Create LIDAR
    config = DistanceSensorConfig(sensor_type="lidar", max_range=12.0)
    lidar = LIDARSensor(config)
    
    # Create obstacles
    obstacles = [
        (np.array([3, 2, 0]), 0.5),   # (position, radius)
        (np.array([5, -1, 0]), 0.3),
        (np.array([2, 4, 0]), 0.4),
    ]
    
    print("\nSimulating LIDAR scan...")
    
    scan = lidar.simulate_scan(time.time(), obstacles)
    print(f"  {len(scan)} points in scan")
    
    # Get point cloud
    points = lidar.get_point_cloud()
    print(f"  Point cloud: {points.shape[0]} points")
    
    # Detect edges
    edges = lidar.detect_edges(threshold=0.3)
    print(f"  Edges detected: {len(edges)}")
    
    # Obstacle map
    print("\n" + "=" * 40)
    print("Obstacle Map")
    print("=" * 40)
    
    obstacle_map = ObstacleMap(resolution=0.2, size=(50, 50, 10))
    
    # Update map
    sensor_pos = np.array([0, 0, 1.0])  # 1m height
    sensor_ori = np.array([1, 0, 0, 0])  # Identity quaternion
    
    obstacle_map.update_from_scan(scan, sensor_pos, sensor_ori)
    print(f"  Map updated with {obstacle_map.update_count} scans")
    
    # Check collision
    test_pos = np.array([2.5, 1.5, 1.0])
    collision, dist = obstacle_map.check_collision(test_pos, radius=0.3)
    print(f"  Collision check at {test_pos}: collision={collision}, dist={dist:.2f}m")
    
    # Ultrasonic demo
    print("\n" + "=" * 40)
    print("Ultrasonic Sensor")
    print("=" * 40)
    
    ultrasonic = UltrasonicSensor()
    
    for true_dist in [0.5, 1.0, 2.0, 3.5]:
        measured = ultrasonic.measure(true_dist, temperature=25)
        valid = ultrasonic.check_valid_measurement(measured)
        print(f"  True: {true_dist:.2f}m -> Measured: {measured:.3f}m (valid: {valid})")
    
    # ToF sensor
    print("\n" + "=" * 40)
    print("ToF Sensor")
    print("=" * 40)
    
    tof = ToFSensor()
    
    # Simulate depth image
    depth_map = np.ones((240, 176)) * 3.0
    depth_map[100:140, 80:96] = 1.5  # Object at 1.5m
    
    depth_image = tof.generate_depth_image(depth_map)
    print(f"  Depth image shape: {depth_image.shape}")
    
    point_cloud = tof.depth_to_point_cloud(depth_image)
    print(f"  Point cloud: {point_cloud.shape[0]} points")


if __name__ == "__main__":
    demo_distance_sensors()