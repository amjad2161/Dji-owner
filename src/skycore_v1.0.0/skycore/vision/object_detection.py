"""Object detection for computer vision."""

import time
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class DetectionClass(Enum):
    """Detection class types."""
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
    center: Tuple[float, float] = None
    
    def __post_init__(self):
        if self.center is None:
            x1, y1, x2, y2 = self.bbox
            self.center = ((x1 + x2) / 2, (y1 + y2) / 2)
    
    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1) * (y2 - y1)


class ObjectDetector(LoggerMixin):
    """Object detector using YOLO or similar models."""
    
    def __init__(self, model_path: Optional[str] = None, conf_threshold: float = 0.25):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.model = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the detector model."""
        if self._initialized:
            return
        
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path or "yolov8n.pt")
            self._initialized = True
            logger.info("Object detector initialized")
        except ImportError:
            logger.warning("ultralytics not available, detector unavailable")
            self._initialized = True  # Allow to run without model
    
    async def detect(self, frame: np.ndarray) -> List[Detection]:
        """Detect objects in frame."""
        if not self._initialized:
            await self.initialize()
        
        detections = []
        
        if self.model is not None:
            try:
                results = self.model(frame, conf=self.conf_threshold, verbose=False)
                for result in results:
                    for box in result.boxes:
                        det = Detection(
                            class_id=int(box.cls[0]),
                            class_name=result.names[int(box.cls[0])],
                            confidence=float(box.conf[0]),
                            bbox=tuple(map(int, box.xyxy[0].tolist()))
                        )
                        detections.append(det)
            except Exception as e:
                logger.error(f"Detection error: {e}")
        
        return detections
    
    async def detect_classes(self, frame: np.ndarray, classes: List[str]) -> List[Detection]:
        """Detect only specific classes."""
        all_detections = await self.detect(frame)
        return [d for d in all_detections if d.class_name in classes]
    
    def get_largest_detection(self, detections: List[Detection]) -> Optional[Detection]:
        """Get the largest detection by area."""
        if not detections:
            return None
        return max(detections, key=lambda d: d.area)
    
    def filter_by_confidence(self, detections: List[Detection], min_conf: float) -> List[Detection]:
        """Filter detections by minimum confidence."""
        return [d for d in detections if d.confidence >= min_conf]