"""Tracker wrapping `boxmot` for multi-object tracking.

Uses BoT-SORT by default; ByteTrack and OC-SORT also available via the
same interface. Maintains track IDs across frames so the visual-follow
controller can stay locked on a chosen subject.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from skycore.vision.detector import Detection

log = logging.getLogger(__name__)


@dataclass
class Track:
    id: int
    detection: Detection


class ObjectTracker:
    def __init__(self, algorithm: str = "botsort"):
        self.algorithm = algorithm
        self._tracker = None
        self._next_id = 1
        # Simple fallback IoU tracker if boxmot isn't installed.
        self._fallback_active: list[Track] = []

    def update(self, detections: list[Detection], frame=None) -> list[Track]:
        if self._tracker is None:
            try:
                self._init_boxmot()
            except ImportError:
                return self._fallback_update(detections)

        import numpy as np
        if not detections:
            return []

        det_array = np.array(
            [[d.x1, d.y1, d.x2, d.y2, d.conf, d.cls] for d in detections],
            dtype=float,
        )
        out_tracks = self._tracker.update(det_array, frame)
        result = []
        for t in out_tracks:
            tid = int(t[4])
            x1, y1, x2, y2 = t[0], t[1], t[2], t[3]
            cls = int(t[5]) if len(t) > 5 else 0
            result.append(
                Track(
                    id=tid,
                    detection=Detection(
                        cls=cls,
                        label=str(cls),
                        conf=1.0,
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                    ),
                )
            )
        return result

    def _init_boxmot(self) -> None:
        from boxmot import BoTSORT, ByteTrack, OCSORT
        from pathlib import Path
        if self.algorithm == "botsort":
            self._tracker = BoTSORT(reid_weights=Path("osnet_x0_25_msmt17.pt"), device="cpu", half=False)
        elif self.algorithm == "bytetrack":
            self._tracker = ByteTrack()
        elif self.algorithm == "ocsort":
            self._tracker = OCSORT()
        else:
            raise ValueError(f"Unknown tracker algorithm: {self.algorithm}")

    def _fallback_update(self, detections: list[Detection]) -> list[Track]:
        # Naive IoU matching
        new_tracks = []
        used_old = set()
        for d in detections:
            best_iou = 0.0
            best_old: Optional[Track] = None
            for old in self._fallback_active:
                if old.id in used_old:
                    continue
                iou = _iou(d, old.detection)
                if iou > best_iou and iou > 0.3:
                    best_iou = iou
                    best_old = old
            if best_old:
                used_old.add(best_old.id)
                new_tracks.append(Track(id=best_old.id, detection=d))
            else:
                new_tracks.append(Track(id=self._next_id, detection=d))
                self._next_id += 1
        self._fallback_active = new_tracks
        return new_tracks


def _iou(a: Detection, b: Detection) -> float:
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0
