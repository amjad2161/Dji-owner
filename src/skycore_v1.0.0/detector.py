"""Object detection wrapping Ultralytics YOLO.

The detector loads any YOLO weights file (v8, v11, custom) and exposes
a `detect(frame) -> list[Detection]` method usable from the visual-follow
controller. Loading is lazy so the import doesn't fail if Ultralytics
isn't installed — you only pay for it when you actually detect.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class Detection:
    cls: int
    label: str
    conf: float
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


class ObjectDetector:
    def __init__(self, weights: str = "yolov8n.pt", conf: float = 0.3, classes: Optional[list[int]] = None):
        self.weights = weights
        self.conf = conf
        self.classes = classes
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from ultralytics import YOLO
        except ImportError as e:
            raise ImportError(
                "ultralytics is required. Install with: pip install ultralytics"
            ) from e
        self._model = YOLO(self.weights)
        log.info("YOLO loaded: %s", self.weights)

    def detect(self, frame) -> list[Detection]:
        self._load()
        results = self._model(frame, conf=self.conf, verbose=False)
        out: list[Detection] = []
        for r in results:
            names = r.names if hasattr(r, "names") else {}
            for box in r.boxes:
                cls = int(box.cls[0])
                if self.classes and cls not in self.classes:
                    continue
                out.append(
                    Detection(
                        cls=cls,
                        label=names.get(cls, str(cls)),
                        conf=float(box.conf[0]),
                        x1=float(box.xyxy[0][0]),
                        y1=float(box.xyxy[0][1]),
                        x2=float(box.xyxy[0][2]),
                        y2=float(box.xyxy[0][3]),
                    )
                )
        return out
