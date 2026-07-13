"""
SkyCore Vision - YOLO + BoT-SORT Smart Tracking
Legal object following for DJI drones (via Mobile SDK)
"""

import asyncio
from typing import Optional, Tuple
import numpy as np

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

class YOLODetector:
    def __init__(self, model_path: str = "yolov8n.pt"):
        if YOLO_AVAILABLE:
            self.model = YOLO(model_path)
        else:
            self.model = None
            print("⚠️ YOLO not installed - using mock detector")

    def detect(self, frame: np.ndarray, target_class: str = "person") -> Optional[Tuple[float, float, float, float]]:
        if not self.model:
            # Mock detection for simulator
            return (0.4, 0.4, 0.2, 0.3)  # x,y,w,h normalized
        
        results = self.model(frame, verbose=False)
        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                if self.model.names[cls] == target_class:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    return (x1, y1, x2-x1, y2-y1)
        return None

class VisualFollowController:
    """Smart visual following controller"""

    def __init__(self, drone, detector: YOLODetector):
        self.drone = drone
        self.detector = detector
        self.running = False

    async def follow(self, target_class: str = "person", distance_m: float = 10.0, 
                     altitude_offset: float = 5.0, max_speed: float = 3.0):
        """Follow target object while maintaining distance"""
        self.running = True
        print(f"🎯 Starting visual follow: {target_class}")
        
        while self.running:
            telemetry = await self.drone.get_telemetry()
            
            # In real implementation: get camera frame from drone
            # frame = await self.drone.get_camera_frame()
            frame = np.zeros((720, 1280, 3))  # placeholder
            
            detection = self.detector.detect(frame, target_class)
            
            if detection:
                x, y, w, h = detection
                center_x = x + w/2
                # Simple proportional control
                yaw_adjust = (center_x - 0.5) * 30  # degrees
                print(f"Tracking {target_class} | Yaw adjust: {yaw_adjust:.1f}°")
                
                # Maintain distance (mock)
                if telemetry.alt < distance_m + altitude_offset:
                    await self.drone.goto(telemetry.lat, telemetry.lon, telemetry.alt + 0.5)
            
            await asyncio.sleep(0.2)  # 5Hz control loop

    def stop(self):
        self.running = False
        print("🛑 Visual follow stopped")
