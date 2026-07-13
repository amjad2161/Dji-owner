"""
SkyCore Vision - YOLO Object Detector
======================================
Real-time object detection using YOLO (You Only Look Once).
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

log = logging.getLogger(__name__)


class YOLOVersion(Enum):
    """YOLO model versions."""
    YOLOv5 = "yolov5"
    YOLOv7 = "yolov7"
    YOLOv8 = "yolov8"
    YOLOv9 = "yolov9"


class DetectionClass(Enum):
    """Common detection classes for drone operations."""
    PERSON = "person"
    VEHICLE = "vehicle"
    ANIMAL = "animal"
    BUILDING = "building"
    OBSTACLE = "obstacle"
    OTHER = "other"


@dataclass
class Detection:
    """Single object detection result."""
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    center: Tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))
    area: float = 0.0
    
    def __post_init__(self):
        x1, y1, x2, y2 = self.bbox
        self.center = ((x1 + x2) / 2, (y1 + y2) / 2)
        self.area = (x2 - x1) * (y2 - y1)
    
    def to_dict(self) -> Dict:
        return {
            'class_id': self.class_id,
            'class_name': self.class_name,
            'confidence': self.confidence,
            'bbox': self.bbox,
            'center': self.center,
            'area': self.area
        }


@dataclass
class DetectionResult:
    """YOLO detection result for a frame."""
    detections: List[Detection]
    timestamp: float = field(default_factory=time.time)
    frame_id: int = 0
    processing_time_ms: float = 0.0
    
    @property
    def person_count(self) -> int:
        return sum(1 for d in self.detections if d.class_name.lower() in ['person', 'human'])
    
    @property
    def vehicle_count(self) -> int:
        return sum(1 for d in self.detections if d.class_name.lower() in ['car', 'truck', 'bus', 'vehicle'])
    
    def get_largest(self, class_filter: Optional[str] = None) -> Optional[Detection]:
        """Get largest detection optionally filtered by class."""
        filtered = self.detections
        if class_filter:
            filtered = [d for d in filtered if class_filter.lower() in d.class_name.lower()]
        
        if not filtered:
            return None
        return max(filtered, key=lambda d: d.area)
    
    def get_by_class(self, class_name: str) -> List[Detection]:
        """Get all detections of a specific class."""
        return [d for d in self.detections if class_name.lower() in d.class_name.lower()]


class YOLODetector:
    """
    YOLO object detector for real-time drone vision.
    
    Supports YOLOv5, YOLOv7, YOLOv8, and YOLOv9 with automatic model download.
    
    Features:
    - Multi-class detection (person, vehicle, animal, obstacle)
    - Confidence filtering
    - NMS (Non-Maximum Suppression)
    - Async frame processing
    - GPU acceleration (CUDA)
    """
    
    # COCO class names for common detection
    COCO_CLASSES = {
        0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 4: 'airplane',
        5: 'bus', 6: 'train', 7: 'truck', 8: 'boat', 9: 'traffic light',
        10: 'fire hydrant', 11: 'stop sign', 12: 'parking meter', 13: 'bench',
        14: 'bird', 15: 'cat', 16: 'dog', 17: 'horse', 18: 'sheep', 19: 'cow',
        20: 'elephant', 21: 'bear', 22: 'zebra', 23: 'giraffe', 24: 'backpack',
        25: 'umbrella', 26: 'handbag', 27: 'tie', 28: 'suitcase', 29: 'frisbee',
        30: 'skis', 31: 'snowboard', 32: 'sports ball', 33: 'kite', 34: 'baseball bat',
        35: 'baseball glove', 36: 'skateboard', 37: 'surfboard', 38: 'tennis racket',
        39: 'bottle', 40: 'wine glass', 41: 'cup', 42: 'fork', 43: 'knife',
        44: 'spoon', 45: 'bowl', 46: 'banana', 47: 'apple', 48: 'sandwich',
        49: 'orange', 50: 'broccoli', 51: 'carrot', 52: 'hot dog', 53: 'pizza',
        54: 'donut', 55: 'cake', 56: 'chair', 57: 'couch', 58: 'potted plant',
        59: 'bed', 60: 'dining table', 61: 'toilet', 62: 'tv', 63: 'laptop',
        64: 'mouse', 65: 'remote', 66: 'keyboard', 67: 'cell phone', 68: 'microwave',
        69: 'oven', 70: 'toaster', 71: 'sink', 72: 'refrigerator', 73: 'book',
        74: 'clock', 75: 'vase', 76: 'scissors', 77: 'teddy bear', 78: 'hair drier',
        79: 'toothbrush'
    }
    
    # Classes relevant for drone operations
    DRONE_CLASSES = [0, 1, 2, 3, 5, 6, 7, 15, 16, 17]  # person, bicycle, car, motorcycle, bus, train, truck, cat, dog, horse
    
    def __init__(self, model_size: str = "yolov8n", conf_threshold: float = 0.25,
                 iou_threshold: float = 0.45, device: str = "auto"):
        """
        Initialize YOLO detector.
        
        Args:
            model_size: Model size (yolov5n/s/m/l, yolov8n/s/m/l, etc.)
            conf_threshold: Confidence threshold for detections
            iou_threshold: IoU threshold for NMS
            device: Device for inference ('auto', 'cuda', 'cpu')
        """
        self.model_size = model_size
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.device = device
        
        self.model = None
        self._initialized = False
        self._model_version = self._detect_version()
        
        # Statistics
        self.frames_processed = 0
        self.total_inference_time = 0.0
        self.detection_counts = {}
        
        # Callbacks
        self._detection_callbacks: List[callable] = []
        
        log.info(f"YOLODetector initialized with {model_size}")
    
    def _detect_version(self) -> YOLOVersion:
        """Detect YOLO version from model name."""
        model_lower = self.model_size.lower()
        if 'v9' in model_lower:
            return YOLOVersion.YOLOv9
        elif 'v8' in model_lower:
            return YOLOVersion.YOLOv8
        elif 'v7' in model_lower:
            return YOLOVersion.YOLOv7
        else:
            return YOLOVersion.YOLOv5
    
    async def initialize(self):
        """Initialize YOLO model."""
        if self._initialized:
            return
        
        try:
            # Try ultralytics (YOLOv8)
            from ultralytics import YOLO
            self.model = YOLO(self.model_size)
            
            # Set device
            if self.device == "auto":
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            
            self.model.to(self.device)
            self._initialized = True
            log.info(f"YOLO {self.model_size} loaded on {self.device}")
            
        except ImportError:
            try:
                # Try yolov5
                import torch
                self.model = torch.hub.load('ultralytics/yolov5', self.model_size)
                self.model.conf = self.conf_threshold
                self.model.iou = self.iou_threshold
                if self.device == "cuda":
                    self.model.cuda()
                self._initialized = True
                log.info(f"YOLOv5 {self.model_size} loaded")
            except Exception as e:
                log.error(f"Failed to load YOLO model: {e}")
                self._initialized = True  # Allow fallback
    
    async def detect(self, frame: np.ndarray) -> DetectionResult:
        """
        Detect objects in frame.
        
        Args:
            frame: RGB image as numpy array (H, W, C)
            
        Returns:
            DetectionResult with all detections
        """
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        
        detections = []
        
        if self.model is not None:
            try:
                if self._model_version == YOLOVersion.YOLOv8:
                    results = self.model(frame, conf=self.conf_threshold, 
                                        iou=self.iou_threshold, verbose=False)
                    
                    for result in results:
                        boxes = result.boxes
                        for box in boxes:
                            det = Detection(
                                class_id=int(box.cls[0]),
                                class_name=self.COCO_CLASSES.get(int(box.cls[0]), 'unknown'),
                                confidence=float(box.conf[0]),
                                bbox=tuple(map(int, box.xyxy[0].tolist()))
                            )
                            detections.append(det)
                            
                elif self._model_version == YOLOVersion.YOLOv5:
                    results = self.model(frame)
                    for *box, conf, cls in results.xyxy[0]:
                        det = Detection(
                            class_id=int(cls),
                            class_name=self.COCO_CLASSES.get(int(cls), 'unknown'),
                            confidence=float(conf),
                            bbox=tuple(map(int, box))
                        )
                        detections.append(det)
                        
            except Exception as e:
                log.error(f"YOLO detection error: {e}")
        
        processing_time = (time.time() - start_time) * 1000
        self.frames_processed += 1
        self.total_inference_time += processing_time
        
        # Update detection counts
        for d in detections:
            class_name = d.class_name
            self.detection_counts[class_name] = self.detection_counts.get(class_name, 0) + 1
        
        result = DetectionResult(
            detections=detections,
            processing_time_ms=processing_time,
            frame_id=self.frames_processed
        )
        
        # Call callbacks
        for callback in self._detection_callbacks:
            try:
                callback(result)
            except Exception as e:
                log.error(f"Detection callback error: {e}")
        
        return result
    
    async def detect_stream(self, frame_queue: asyncio.Queue,
                           result_queue: asyncio.Queue):
        """
        Process frames from queue and put results in result queue.
        
        Args:
            frame_queue: Input queue with frames
            result_queue: Output queue with DetectionResults
        """
        while True:
            try:
                item = await frame_queue.get()
                if item is None:
                    break
                
                frame, frame_id = item
                result = await self.detect(frame)
                result.frame_id = frame_id
                await result_queue.put(result)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Detect stream error: {e}")
    
    def on_detection(self, callback: callable):
        """Register detection callback."""
        self._detection_callbacks.append(callback)
    
    def apply_nms(self, detections: List[Detection]) -> List[Detection]:
        """
        Apply Non-Maximum Suppression to detections.
        
        Args:
            detections: List of detections
            
        Returns:
            Filtered detections after NMS
        """
        if not detections:
            return []
        
        boxes = np.array([d.bbox for d in detections])
        scores = np.array([d.confidence for d in detections])
        
        # Compute IoU matrix
        iou_matrix = self._compute_iou_matrix(boxes)
        
        # NMS
        keep = []
        order = scores.argsort()[::-1]
        
        while order.size > 0:
            i = order[0]
            keep.append(i)
            
            if order.size == 1:
                break
            
            ious = iou_matrix[i, order[1:]]
            mask = ious <= self.iou_threshold
            order = order[1:][mask]
        
        return [detections[i] for i in keep]
    
    def _compute_iou_matrix(self, boxes: np.ndarray) -> np.ndarray:
        """Compute IoU matrix for boxes."""
        n = len(boxes)
        iou_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(n):
                x1 = max(boxes[i][0], boxes[j][0])
                y1 = max(boxes[i][1], boxes[j][1])
                x2 = min(boxes[i][2], boxes[j][2])
                y2 = min(boxes[i][3], boxes[j][3])
                
                inter = max(0, x2 - x1) * max(0, y2 - y1)
                area_i = (boxes[i][2] - boxes[i][0]) * (boxes[i][3] - boxes[i][1])
                area_j = (boxes[j][2] - boxes[j][0]) * (boxes[j][3] - boxes[j][1])
                union = area_i + area_j - inter
                
                iou_matrix[i, j] = inter / union if union > 0 else 0
        
        return iou_matrix
    
    def filter_by_class(self, detections: List[Detection], 
                       classes: List[str]) -> List[Detection]:
        """Filter detections by class names."""
        return [d for d in detections if d.class_name in classes]
    
    def filter_by_confidence(self, detections: List[Detection],
                            min_conf: float) -> List[Detection]:
        """Filter detections by minimum confidence."""
        return [d for d in detections if d.confidence >= min_conf]
    
    def filter_by_area(self, detections: List[Detection],
                      min_area: float, max_area: float = float('inf')) -> List[Detection]:
        """Filter detections by area range."""
        return [d for d in detections if min_area <= d.area <= max_area]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return {
            'frames_processed': self.frames_processed,
            'total_inference_time_ms': round(self.total_inference_time, 2),
            'average_inference_ms': round(self.total_inference_time / max(1, self.frames_processed), 2),
            'model_size': self.model_size,
            'device': self.device,
            'conf_threshold': self.conf_threshold,
            'iou_threshold': self.iou_threshold,
            'detection_counts': self.detection_counts,
            'initialized': self._initialized
        }


class YOLOv8Detector(YOLODetector):
    """YOLOv8 specific detector with optimized settings."""
    
    def __init__(self, model_size: str = "yolov8n", conf_threshold: float = 0.25,
                 iou_threshold: float = 0.45):
        super().__init__(f"yolov8{model_size[-1]}" if model_size.startswith('yolov8') else model_size,
                        conf_threshold, iou_threshold)


class YOLOv5Detector(YOLODetector):
    """YOLOv5 specific detector."""
    
    def __init__(self, model_size: str = "yolov5s", conf_threshold: float = 0.25,
                 iou_threshold: float = 0.45):
        super().__init__(model_size, conf_threshold, iou_threshold)


# Export
__all__ = ['YOLODetector', 'YOLOv8Detector', 'YOLOv5Detector', 'Detection', 'DetectionResult', 'YOLOVersion', 'DetectionClass']