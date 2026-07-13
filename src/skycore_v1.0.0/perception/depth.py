"""Depth estimation from multiple sensor sources.

Implements:
- Stereo matching
- Multi-view geometry
- LIDAR-camera fusion
- Depth map refinement
- 3D reconstruction
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
import numpy as np
from numpy.typing import NDArray
import cv2


@dataclass
class DepthConfig:
    """Depth estimation configuration."""
    # Camera parameters
    baseline: float = 0.12   # meters (stereo baseline)
    focal_length: float = 800  # pixels
    
    # Stereo matching
    algorithm: str = "sgbm"  # "sgbm", "bm", "raft"
    max_disparity: int = 256
    block_size: int = 9
    
    # Fusion
    use_lidar: bool = True
    lidar_weight: float = 0.7
    
    # Refinement
    median_filter_size: int = 5
    bilateral_sigma: float = 20.0


@dataclass
class DepthMap:
    """Combined depth map with confidence."""
    depth: NDArray       # Depth values in meters
    confidence: NDArray # 0-1 confidence values
    
    # Metadata
    timestamp: float = 0.0
    resolution: Tuple[int, int] = (0, 0)
    min_depth: float = 0.0
    max_depth: float = 100.0


class StereoMatcher:
    """Stereo matching for depth estimation."""
    
    def __init__(self, config: Optional[DepthConfig] = None):
        self.config = config or DepthConfig()
        
        # SGBM parameters
        self.min_disparity = 0
        self.num_disparities = config.max_disparity if config else 256
        self.block_size = config.block_size if config else 9
        
        # Create matcher
        self.matcher = cv2.StereoSGBM_create(
            minDisparity=self.min_disparity,
            numDisparities=self.num_disparities,
            blockSize=self.block_size,
            P1=8 * 3 * self.block_size ** 2,
            P2=32 * 3 * self.block_size ** 2,
            disp12MaxDiff=1,
            uniquenessRatio=15,
            speckleWindowSize=100,
            speckleRange=32,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
        )
    
    def match(self, left_image: NDArray, right_image: NDArray) -> NDArray:
        """Compute disparity map from stereo pair.
        
        Args:
            left_image: Left camera image
            right_image: Right camera image
            
        Returns:
            Disparity map (pixels)
        """
        # Ensure grayscale
        if len(left_image.shape) == 3:
            left_gray = cv2.cvtColor(left_image, cv2.COLOR_BGR2GRAY)
            right_gray = cv2.cvtColor(right_image, cv2.COLOR_BGR2GRAY)
        else:
            left_gray = left_image
            right_gray = right_image
        
        # Compute disparity
        disparity = self.matcher.compute(left_gray, right_gray)
        
        # Normalize
        disparity = np.clip(disparity, 0, self.num_disparities)
        
        return disparity
    
    def disparity_to_depth(self, disparity: NDArray) -> NDArray:
        """Convert disparity to depth.
        
        depth = baseline * focal / disparity
        """
        baseline = self.config.baseline
        focal = self.config.focal_length
        
        # Avoid division by zero
        depth = np.zeros_like(disparity, dtype=np.float32)
        valid = disparity > 0
        
        depth[valid] = baseline * focal / disparity[valid]
        
        # Clamp to reasonable range
        depth = np.clip(depth, 0.1, 100.0)
        
        return depth


class LIDARDepthFusion:
    """Fuse LIDAR points with camera depth map."""
    
    def __init__(self, config: Optional[DepthConfig] = None):
        self.config = config or DepthConfig()
        
        self.point_cloud: List[NDArray] = []
        self.max_points = 5000
    
    def add_lidar_points(
        self,
        points: NDArray,
        image: NDArray,
        intrinsics: Dict
    ) -> None:
        """Add LIDAR points to fusion buffer.
        
        Args:
            points: Nx3 LIDAR points (x, y, z in camera frame)
            image: Camera image for projection
            intrinsics: Camera intrinsics (fx, fy, cx, cy)
        """
        self.point_cloud.append(points.copy())
        
        if len(self.point_cloud) > self.max_points:
            self.point_cloud.pop(0)
    
    def fuse(
        self,
        camera_depth: NDArray,
        intrinsics: Dict
    ) -> Tuple[NDArray, NDArray]:
        """Fuse camera depth with LIDAR points.
        
        Args:
            camera_depth: Depth map from camera
            intrinsics: Camera intrinsics
            
        Returns:
            (fused_depth, confidence)
        """
        h, w = camera_depth.shape
        fused_depth = camera_depth.copy()
        confidence = np.ones_like(camera_depth, dtype=np.float32) * 0.5
        
        fx = intrinsics.get('fx', 500)
        fy = intrinsics.get('fy', 500)
        cx = intrinsics.get('cx', w // 2)
        cy = intrinsics.get('cy', h // 2)
        
        # Project LIDAR points to image
        for points in self.point_cloud:
            for point in points:
                x, y, z = point
                
                if z <= 0:
                    continue
                
                # Project to image
                u = int(x * fx / z + cx)
                v = int(y * fy / z + cy)
                
                if 0 <= u < w and 0 <= v < h:
                    # Update depth at this pixel
                    if fused_depth[v, u] > z or fused_depth[v, u] < 0.1:
                        fused_depth[v, u] = z
                        confidence[v, u] = self.config.lidar_weight
        
        return fused_depth, confidence
    
    def create_depth_map_from_points(
        self,
        points: NDArray,
        intrinsics: Dict,
        image_size: Tuple[int, int]
    ) -> NDArray:
        """Create dense depth map from sparse LIDAR points.
        
        Args:
            points: Nx3 points
            intrinsics: Camera intrinsics
            image_size: (width, height)
            
        Returns:
            Dense depth map
        """
        w, h = image_size
        depth_map = np.zeros((h, w), dtype=np.float32)
        count_map = np.zeros((h, w), dtype=np.float32)
        
        fx = intrinsics.get('fx', 500)
        fy = intrinsics.get('fy', 500)
        cx = intrinsics.get('cx', w // 2)
        cy = intrinsics.get('cy', h // 2)
        
        for point in points:
            x, y, z = point
            
            if z <= 0.1:
                continue
            
            u = int(x * fx / z + cx)
            v = int(y * fy / z + cy)
            
            if 0 <= u < w and 0 <= v < h:
                # Accumulate depth values
                depth_map[v, u] += z
                count_map[v, u] += 1
        
        # Average
        valid = count_map > 0
        depth_map[valid] /= count_map[valid]
        
        # Fill holes using inpainting
        depth_map = self._fill_holes(depth_map)
        
        return depth_map
    
    def _fill_holes(self, depth: NDArray) -> NDArray:
        """Fill holes in depth map."""
        # Create mask of invalid pixels
        mask = (depth > 0).astype(np.uint8)
        
        # Inpaint using fast marching
        h, w = depth.shape
        filled = depth.copy()
        
        # Simple nearest-neighbor fill
        for v in range(h):
            for u in range(w):
                if depth[v, u] < 0.1:
                    # Find nearest valid pixel
                    best_dist = float('inf')
                    best_depth = 0
                    
                    for dv in range(-20, 21):
                        for du in range(-20, 21):
                            nv, nu = v + dv, u + du
                            
                            if 0 <= nv < h and 0 <= nu < w:
                                if depth[nv, nu] > 0.1:
                                    dist = dv**2 + du**2
                                    if dist < best_dist:
                                        best_dist = dist
                                        best_depth = depth[nv, nu]
                    
                    filled[v, u] = best_depth
        
        return filled


class DepthRefinement:
    """Refine depth map using filtering and edge-aware processing."""
    
    def __init__(self, config: Optional[DepthConfig] = None):
        self.config = config or DepthConfig()
    
    def bilateral_filter(
        self,
        depth: NDArray,
        spatial_sigma: float = 10,
        range_sigma: float = 0.1
    ) -> NDArray:
        """Apply bilateral filter to depth map.
        
        Args:
            depth: Input depth
            spatial_sigma: Spatial kernel size
            range_sigma: Range kernel size
            
        Returns:
            Filtered depth
        """
        # Use OpenCV bilateral filter
        filtered = cv2.bilateralFilter(
            depth.astype(np.float32),
            ksize=int(spatial_sigma),
            sigmaColor=range_sigma
        )
        
        return filtered
    
    def median_filter(self, depth: NDArray, kernel_size: int = 5) -> NDArray:
        """Apply median filter to remove outliers."""
        return cv2.medianBlur(depth.astype(np.float32), kernel_size)
    
    def temporal_median(
        self,
        depth_maps: List[NDArray],
        weights: Optional[List[float]] = None
    ) -> NDArray:
        """Compute temporal median from sequence of depth maps.
        
        Args:
            depth_maps: List of depth maps
            weights: Optional weights for each map
            
        Returns:
            Median depth
        """
        if not depth_maps:
            return np.zeros((480, 640))
        
        # Stack
        depth_stack = np.stack(depth_maps, axis=0)
        
        if weights is not None:
            # Weighted median
            weights_arr = np.array(weights)[:, None, None]
            weighted = depth_stack * weights_arr
            result = np.median(weighted, axis=0)
        else:
            result = np.median(depth_stack, axis=0)
        
        return result
    
    def confidence_weighted_average(
        self,
        depth_maps: List[NDArray],
        confidences: List[NDArray]
    ) -> NDArray:
        """Weighted average based on confidence."""
        if not depth_maps:
            return np.zeros((480, 640))
        
        numerator = np.zeros_like(depth_maps[0])
        denominator = np.zeros_like(depth_maps[0])
        
        for depth, conf in zip(depth_maps, confidences):
            numerator += depth * conf
            denominator += conf
        
        result = np.zeros_like(depth_maps[0])
        valid = denominator > 0
        result[valid] = numerator[valid] / denominator[valid]
        
        return result


class DepthEstimator:
    """Complete depth estimation pipeline."""
    
    def __init__(self, config: Optional[DepthConfig] = None):
        self.config = config or DepthConfig()
        
        # Components
        self.stereo = StereoMatcher(config)
        self.lidar_fusion = LIDARDepthFusion(config)
        self.refinement = DepthRefinement(config)
        
        # State
        self.depth_history: List[DepthMap] = []
        self.max_history = 30
    
    def estimate_from_stereo(
        self,
        left_image: NDArray,
        right_image: NDArray
    ) -> DepthMap:
        """Estimate depth from stereo pair.
        
        Args:
            left_image: Left camera image
            right_image: Right camera image
            
        Returns:
            DepthMap
        """
        # Compute disparity
        disparity = self.stereo.match(left_image, right_image)
        
        # Convert to depth
        depth = self.stereo.disparity_to_depth(disparity)
        
        # Compute confidence from disparity
        confidence = np.clip(disparity / self.config.max_disparity, 0, 1)
        
        # Refine
        depth = self.refinement.median_filter(depth, self.config.median_filter_size)
        depth = self.refinement.bilateral_filter(depth, spatial_sigma=self.config.bilateral_sigma)
        
        return DepthMap(
            depth=depth,
            confidence=confidence,
            timestamp=0,
            resolution=depth.shape[:2][::-1],
            min_depth=depth.min(),
            max_depth=depth.max()
        )
    
    def estimate_from_lidar(
        self,
        lidar_points: NDArray,
        intrinsics: Dict,
        image_size: Tuple[int, int]
    ) -> DepthMap:
        """Estimate depth from LIDAR points.
        
        Args:
            lidar_points: Nx3 LIDAR points
            intrinsics: Camera intrinsics
            image_size: (width, height)
            
        Returns:
            DepthMap
        """
        depth = self.lidar_fusion.create_depth_map_from_points(
            lidar_points, intrinsics, image_size
        )
        
        # Confidence based on point density
        confidence = np.clip(depth / 20.0, 0, 1)
        
        return DepthMap(
            depth=depth,
            confidence=confidence,
            timestamp=0,
            resolution=image_size,
            min_depth=depth.min() if depth.max() > 0 else 0,
            max_depth=depth.max()
        )
    
    def fuse_depth_maps(
        self,
        camera_depth: NDArray,
        camera_confidence: NDArray,
        lidar_depth: NDArray,
        lidar_confidence: NDArray
    ) -> DepthMap:
        """Fuse camera and LIDAR depth maps.
        
        Args:
            camera_depth: Depth from camera
            camera_confidence: Camera depth confidence
            lidar_depth: Depth from LIDAR
            lidar_confidence: LIDAR confidence
            
        Returns:
            Fused DepthMap
        """
        # Weight by confidence
        total_confidence = camera_confidence + lidar_confidence
        
        fused = np.zeros_like(camera_depth)
        valid = total_confidence > 0
        
        fused[valid] = (
            camera_depth[valid] * camera_confidence[valid] +
            lidar_depth[valid] * lidar_confidence[valid]
        ) / total_confidence[valid]
        
        # Refine
        fused = self.refinement.bilateral_filter(fused, spatial_sigma=5)
        
        return DepthMap(
            depth=fused,
            confidence=total_confidence / 2,  # Normalize
            timestamp=0,
            resolution=fused.shape[:2][::-1],
            min_depth=fused.min(),
            max_depth=fused.max()
        )
    
    def get_obstacle_distances(
        self,
        depth_map: DepthMap,
        directions: List[NDArray],
        fov: float = 1.0
    ) -> Dict[str, float]:
        """Get distances to obstacles in given directions.
        
        Args:
            depth_map: Current depth map
            directions: List of direction vectors
            fov: Field of view per direction (radians)
            
        Returns:
            Dictionary of direction name to distance
        """
        h, w = depth_map.depth.shape
        cx, cy = w // 2, h // 2
        
        distances = {}
        
        for direction in directions:
            # Ray in image
            dx, dy, dz = direction
            
            if abs(dz) < 0.01:
                continue
            
            # Project to image
            u = int(cx + dx * 100 / dz)
            v = int(cy + dy * 100 / dz)
            
            if 0 <= u < w and 0 <= v < h:
                distances[f"dir_{dx:.1f}_{dy:.1f}"] = depth_map.depth[v, u]
        
        return distances


def demo_depth():
    """Demonstrate depth estimation."""
    print("=" * 60)
    print("Depth Estimation Demo")
    print("=" * 60)
    
    # Create estimator
    config = DepthConfig(baseline=0.12, focal_length=800)
    estimator = DepthEstimator(config)
    
    # Simulate stereo images
    print("\nEstimating from stereo...")
    
    left = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    right = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    depth_map = estimator.estimate_from_stereo(left, right)
    
    print(f"  Depth range: {depth_map.min_depth:.2f} - {depth_map.max_depth:.2f}m")
    print(f"  Resolution: {depth_map.resolution}")
    
    # LIDAR fusion
    print("\n" + "=" * 40)
    print("LIDAR Fusion")
    print("=" * 40)
    
    # Generate random LIDAR points
    points = np.random.randn(1000, 3)
    points[:, 2] = np.abs(points[:, 2]) + 1  # Positive Z
    
    intrinsics = {'fx': 500, 'fy': 500, 'cx': 320, 'cy': 240}
    
    lidar_depth = estimator.estimate_from_lidar(points, intrinsics, (640, 480))
    print(f"  LIDAR depth range: {lidar_depth.min_depth:.2f} - {lidar_depth.max_depth:.2f}m")
    
    # Fuse
    print("\n" + "=" * 40)
    print("Depth Fusion")
    print("=" * 40)
    
    fused = estimator.fuse_depth_maps(
        depth_map.depth, depth_map.confidence,
        lidar_depth.depth, lidar_depth.confidence
    )
    
    print(f"  Fused depth range: {fused.min_depth:.2f} - {fused.max_depth:.2f}m")
    print(f"  Average confidence: {np.mean(fused.confidence):.2f}")
    
    # Obstacle distances
    print("\n" + "=" * 40)
    print("Obstacle Distances")
    print("=" * 40)
    
    directions = [
        np.array([0, 0, 1]),      # Forward
        np.array([1, 0, 1]),      # Forward-right
        np.array([-1, 0, 1]),     # Forward-left
        np.array([0, 1, 1]),      # Right
        np.array([0, -1, 1]),     # Left
    ]
    
    distances = estimator.get_obstacle_distances(fused, directions)
    for key, dist in distances.items():
        print(f"  {key}: {dist:.2f}m")


if __name__ == "__main__":
    demo_depth()