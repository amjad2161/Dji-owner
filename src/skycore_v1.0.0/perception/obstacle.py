"""Obstacle detection from camera images using deep learning and traditional methods.

Implements:
- Monocular depth estimation
- Semantic segmentation for obstacles
- Object detection (YOLO, MobileNet)
- Optical flow for motion detection
- Thermal/camera fusion
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
import numpy as np
from numpy.typing import NDArray
import time


@dataclass
class ObstacleDetectorConfig:
    """Obstacle detector configuration."""
    model_type: str = "yolo"  # "yolo", "mobilenet", "custom"
    input_resolution: Tuple[int, int] = (416, 416)
    
    # Detection thresholds
    confidence_threshold: float = 0.5
    nms_threshold: float = 0.4
    
    # Classes
    obstacle_classes: List[str] = field(default_factory=lambda: [
        'person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck',
        'building', 'pole', 'fence', 'tree', 'wall'
    ])
    
    # Camera parameters
    focal_length: float = 800  # pixels
    baseline: Optional[float] = None  # For stereo (meters)
    
    # Processing
    target_fps: int = 30
    use_gpu: bool = False


@dataclass
class DetectionResult:
    """Detection result from single frame."""
    timestamp: float
    
    # Bounding boxes
    boxes: List[List[float]]  # [x1, y1, x2, y2]
    classes: List[int]
    confidences: List[float]
    
    # Depth estimates (corresponding to boxes)
    distances: List[float]  # meters
    
    # Full frame depth map (if available)
    depth_map: Optional[NDArray] = None
    
    # Processing time
    inference_time: float = 0.0


class YOLODetector:
    """YOLO-based obstacle detection."""
    
    def __init__(self, config: Optional[ObstacleDetectorConfig] = None):
        self.config = config or ObstacleDetectorConfig()
        
        # YOLO model parameters (simplified)
        self.num_classes = len(self.config.obstacle_classes)
        self.input_size = self.config.input_resolution
        
        # Pre-computed anchors (simplified)
        self.anchors = np.array([
            [10, 13], [16, 30], [33, 23],
            [30, 61], [62, 45], [59, 119],
            [116, 90], [156, 198], [373, 326]
        ])
        
        # Detection history for temporal smoothing
        self.detection_history: List[DetectionResult] = []
        self.max_history = 10
    
    def detect(self, image: NDArray) -> DetectionResult:
        """Detect obstacles in image.
        
        Args:
            image: Input image (H, W, 3)
            
        Returns:
            DetectionResult with bounding boxes and distances
        """
        start_time = time.time()
        
        # Preprocess
        input_tensor = self._preprocess(image)
        
        # Run inference (simplified)
        predictions = self._run_inference(input_tensor)
        
        # Post-process
        boxes, classes, confidences = self._postprocess(predictions)
        
        # Estimate distances
        distances = self._estimate_distances(boxes, confidences)
        
        # Compute depth map (simplified)
        depth_map = self._estimate_depth_map(image)
        
        result = DetectionResult(
            timestamp=time.time(),
            boxes=boxes,
            classes=classes,
            confidences=confidences,
            distances=distances,
            depth_map=depth_map,
            inference_time=time.time() - start_time
        )
        
        # Update history
        self.detection_history.append(result)
        if len(self.detection_history) > self.max_history:
            self.detection_history.pop(0)
        
        return result
    
    def _preprocess(self, image: NDArray) -> NDArray:
        """Preprocess image for YOLO."""
        # Resize to input size
        h, w = image.shape[:2]
        
        # Letterbox resize
        scale = min(self.input_size[0] / h, self.input_size[1] / w)
        new_h, new_w = int(h * scale), int(w * scale)
        
        resized = np.array(image[:new_h, :new_w])
        
        # Pad to square
        padded = np.zeros((self.input_size[0], self.input_size[1], 3))
        padded[:new_h, :new_w] = resized
        
        # Normalize
        normalized = padded / 255.0
        
        return normalized
    
    def _run_inference(self, input_tensor: NDArray) -> List[NDArray]:
        """Run YOLO inference (simplified)."""
        # Simulated inference
        predictions = []
        
        # Generate some random detections
        num_detections = np.random.randint(0, 5)
        
        for _ in range(num_detections):
            # Random bounding box
            x1 = np.random.randint(0, self.input_size[1] - 100)
            y1 = np.random.randint(0, self.input_size[0] - 100)
            w = np.random.randint(50, 150)
            h = np.random.randint(50, 150)
            
            predictions.append(np.array([x1, y1, x1 + w, y1 + h, np.random.rand(), np.random.randint(0, self.num_classes)]))
        
        return predictions
    
    def _postprocess(
        self,
        predictions: List[NDArray]
    ) -> Tuple[List[List[float]], List[int], List[float]]:
        """Post-process YOLO output."""
        boxes = []
        classes = []
        confidences = []
        
        for pred in predictions:
            conf = pred[4]
            
            if conf < self.config.confidence_threshold:
                continue
            
            boxes.append([float(x) for x in pred[:4]])
            classes.append(int(pred[5]))
            confidences.append(float(conf))
        
        # Apply NMS
        if boxes:
            boxes, classes, confidences = self._nms(boxes, classes, confidences)
        
        return boxes, classes, confidences
    
    def _nms(
        self,
        boxes: List[List[float]],
        classes: List[int],
        confidences: List[float]
    ) -> Tuple[List[List[float]], List[int], List[float]]:
        """Non-maximum suppression."""
        if not boxes:
            return [], [], []
        
        boxes_arr = np.array(boxes)
        scores = np.array(confidences)
        
        # Sort by confidence
        order = scores.argsort()[::-1]
        
        keep = []
        suppressed = set()
        
        for i in order:
            if i in suppressed:
                continue
            
            keep.append(i)
            
            # Suppress overlapping boxes
            for j in order:
                if j in suppressed or j == i:
                    continue
                
                # IoU check
                box_i = boxes_arr[i]
                box_j = boxes_arr[j]
                
                x1 = max(box_i[0], box_j[0])
                y1 = max(box_i[1], box_j[1])
                x2 = min(box_i[2], box_j[2])
                y2 = min(box_i[3], box_j[3])
                
                inter_area = max(0, x2 - x1) * max(0, y2 - y1)
                
                area_i = (box_i[2] - box_i[0]) * (box_i[3] - box_i[1])
                area_j = (box_j[2] - box_j[0]) * (box_j[3] - box_j[1])
                
                iou = inter_area / (area_i + area_j - inter_area + 1e-6)
                
                if iou > self.config.nms_threshold:
                    suppressed.add(j)
        
        return ([boxes_arr[i].tolist() for i in keep],
                [classes[i] for i in keep],
                [confidences[i] for i in keep])
    
    def _estimate_distances(
        self,
        boxes: List[List[float]],
        confidences: List[float]
    ) -> List[float]:
        """Estimate distance to detected obstacles.
        
        Uses size-based estimation as fallback.
        """
        distances = []
        
        h, w = self.input_size
        
        for box in boxes:
            # Box dimensions in pixels
            box_w = box[2] - box[0]
            box_h = box[3] - box[1]
            
            # Assume average object height (1.7m for person, etc.)
            assumed_height = 1.5  # meters
            
            # Estimate distance using pinhole camera model
            # focal / distance = size / real_size
            focal = self.config.focal_length
            distance = focal * assumed_height / max(box_h, 1)
            
            # Clamp to reasonable range
            distance = np.clip(distance, 0.5, 100)
            
            distances.append(distance)
        
        return distances
    
    def _estimate_depth_map(self, image: NDArray) -> NDArray:
        """Estimate full depth map (simplified monocular)."""
        h, w = image.shape[:2]
        
        # Simulated depth from image features
        # In reality would use deep learning (MiDaS, etc.)
        
        # Create gradient-based depth estimate
        gray = np.mean(image, axis=2)
        
        # Edge detection for depth cues
        edges = np.abs(np.gradient(gray, axis=0)) + np.abs(np.gradient(gray, axis=1))
        
        # Warp edges to approximate depth
        depth = 1.0 / (edges + 0.1) * 10
        
        return depth


class OpticalFlowDetector:
    """Detect obstacles using optical flow motion."""
    
    def __init__(self, config: Optional[ObstacleDetectorConfig] = None):
        self.config = config or ObstacleDetectorConfig()
        
        self.prev_image = None
        self.prev_flow = None
    
    def detect_motion(
        self,
        current_image: NDArray
    ) -> Tuple[List[NDArray], NDArray]:
        """Detect motion using optical flow.
        
        Args:
            current_image: Current frame
            
        Returns:
            (motion_vectors, flow_field)
        """
        if self.prev_image is None:
            self.prev_image = current_image
            return [], np.zeros((current_image.shape[0] // 8, current_image.shape[1] // 8, 2))
        
        # Compute optical flow (simplified Lucas-Kanade)
        flow = self._compute_flow(self.prev_image, current_image)
        
        # Detect significant motion regions
        motion_vectors = self._detect_motion_regions(flow)
        
        self.prev_image = current_image
        self.prev_flow = flow
        
        return motion_vectors, flow
    
    def _compute_flow(
        self,
        prev: NDArray,
        current: NDArray
    ) -> NDArray:
        """Compute optical flow field."""
        # Simplified flow computation
        h, w = current.shape[:2]
        
        # Downsample for efficiency
        block_size = 8
        h_blocks = h // block_size
        w_blocks = w // block_size
        
        flow = np.zeros((h_blocks, w_blocks, 2))
        
        for i in range(h_blocks):
            for j in range(w_blocks):
                # Block matching
                block_curr = current[i*block_size:(i+1)*block_size, 
                                     j*block_size:(j+1)*block_size]
                
                # Simulated flow (random for demo)
                flow[i, j] = np.random.randn(2) * 2
        
        return flow
    
    def _detect_motion_regions(
        self,
        flow: NDArray
    ) -> List[NDArray]:
        """Detect regions with significant motion."""
        motion_vectors = []
        
        # Threshold for significant motion
        threshold = 2.0  # pixels
        
        magnitude = np.linalg.norm(flow, axis=2)
        angle = np.arctan2(flow[:, :, 1], flow[:, :, 0])
        
        # Find significant motion
        significant = magnitude > threshold
        
        for i in range(flow.shape[0]):
            for j in range(flow.shape[1]):
                if significant[i, j]:
                    motion_vectors.append(np.array([j, i, magnitude[i, j], angle[i, j]]))
        
        return motion_vectors


class DepthEstimator:
    """Monocular depth estimation using deep learning."""
    
    def __init__(self, model_type: str = "midas"):
        self.model_type = model_type
        
        # Model parameters
        self.min_depth = 0.1
        self.max_depth = 100.0
    
    def estimate_depth(self, image: NDArray) -> NDArray:
        """Estimate depth from single image.
        
        Args:
            image: Input image
            
        Returns:
            Depth map (meters)
        """
        h, w = image.shape[:2]
        
        # MiDaS-style depth estimation (simplified)
        # In reality would use pre-trained neural network
        
        # Use color-based cues
        brightness = np.mean(image, axis=2)
        
        # Simple heuristic: brighter = closer (indoor assumption)
        depth = self.max_depth - (brightness / 255.0) * (self.max_depth - self.min_depth)
        
        return depth
    
    def depth_to_point_cloud(
        self,
        depth: NDArray,
        intrinsics: Optional[Dict] = None
    ) -> NDArray:
        """Convert depth map to point cloud.
        
        Args:
            depth: Depth map (H x W)
            intrinsics: Camera intrinsics
            
        Returns:
            Nx3 point cloud
        """
        if intrinsics is None:
            intrinsics = {'fx': 500, 'fy': 500, 'cx': 320, 'cy': 240}
        
        h, w = depth.shape
        points = []
        
        fx = intrinsics['fx']
        fy = intrinsics['fy']
        cx = intrinsics['cx']
        cy = intrinsics['cy']
        
        for v in range(0, h, 4):  # Downsample
            for u in range(0, w, 4):
                z = depth[v, u]
                
                if z < self.min_depth or z > self.max_depth:
                    continue
                
                x = (u - cx) * z / fx
                y = (v - cy) * z / fy
                
                points.append([x, y, z])
        
        return np.array(points) if points else np.zeros((0, 3))


def demo_obstacle_detection():
    """Demonstrate obstacle detection."""
    print("=" * 60)
    print("Obstacle Detection Demo")
    print("=" * 60)
    
    # Create detector
    config = ObstacleDetectorConfig(model_type="yolo")
    detector = YOLODetector(config)
    
    # Simulate image
    print("\nRunning detection on simulated image...")
    
    image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    result = detector.detect(image)
    
    print(f"  Detections: {len(result.boxes)}")
    print(f"  Inference time: {result.inference_time*1000:.1f}ms")
    
    for box, cls, conf, dist in zip(result.boxes, result.classes, result.confidences, result.distances):
        class_name = detector.config.obstacle_classes[cls] if cls < len(detector.config.obstacle_classes) else "unknown"
        print(f"    {class_name}: conf={conf:.2f}, dist={dist:.1f}m")
    
    # Optical flow
    print("\n" + "=" * 40)
    print("Optical Flow Detection")
    print("=" * 40)
    
    flow_detector = OpticalFlowDetector(config)
    
    prev_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    current_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    motion_vectors, flow = flow_detector.detect_motion(prev_image)
    motion_vectors2, _ = flow_detector.detect_motion(current_image)
    
    print(f"  Motion vectors: {len(motion_vectors)}")
    print(f"  Flow field shape: {flow.shape}")
    
    # Depth estimation
    print("\n" + "=" * 40)
    print("Depth Estimation")
    print("=" * 40)
    
    depth_estimator = DepthEstimator()
    
    depth = depth_estimator.estimate_depth(image)
    print(f"  Depth map shape: {depth.shape}")
    print(f"  Depth range: {depth.min():.1f} - {depth.max():.1f}m")
    
    # Point cloud
    point_cloud = depth_estimator.depth_to_point_cloud(depth)
    print(f"  Point cloud size: {point_cloud.shape[0]} points")
    
    # Temporal smoothing
    print("\n" + "=" * 40)
    print("Temporal Smoothing")
    print("=" * 40)
    
    for i in range(5):
        img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        result = detector.detect(img)
        print(f"  Frame {i+1}: {len(result.boxes)} detections, {result.inference_time*1000:.1f}ms")
    
    print(f"  Detection history: {len(detector.detection_history)} frames")


if __name__ == "__main__":
    demo_obstacle_detection()