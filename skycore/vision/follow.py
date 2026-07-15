"""Visual-follow controller: keeps the drone (and gimbal) locked on a tracked object.

Given a video frame stream and a chosen track ID, the controller computes
pixel-space error from frame center and converts it into:
  - yaw rate command (X error → yaw)
  - gimbal pitch command (Y error → pitch)
  - forward velocity (bbox area → forward/back to maintain distance)

The controller is backend-agnostic; pass any SkyCore Drone instance.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from skycore.core.drone import Drone
from skycore.vision.detector import ObjectDetector
from skycore.vision.tracker import ObjectTracker, Track

log = logging.getLogger(__name__)


@dataclass
class FollowConfig:
    target_class: Optional[int] = None  # 0 = person in COCO
    target_track_id: Optional[int] = None  # if set, lock to this track
    target_bbox_area_ratio: float = 0.10  # area as fraction of frame
    yaw_p: float = 0.15  # deg/sec per pixel of X error
    pitch_p: float = 0.10
    forward_p: float = 0.6  # m/s per unit area error
    yaw_max_rate: float = 30.0
    pitch_max_deg_per_step: float = 2.0
    forward_max_speed: float = 3.0


class VisualFollowController:
    def __init__(
        self,
        drone: Drone,
        detector: ObjectDetector,
        tracker: Optional[ObjectTracker] = None,
        config: Optional[FollowConfig] = None,
    ):
        self.drone = drone
        self.detector = detector
        self.tracker = tracker or ObjectTracker()
        self.config = config or FollowConfig()
        self._gimbal_pitch = 0.0

    async def step(self, frame, frame_w: int, frame_h: int) -> bool:
        """Process one frame. Returns True if a target was followed."""
        detections = self.detector.detect(frame)
        if self.config.target_class is not None:
            detections = [d for d in detections if d.cls == self.config.target_class]
        tracks = self.tracker.update(detections, frame)
        if not tracks:
            return False

        target = self._pick_target(tracks)
        if target is None:
            return False

        det = target.detection
        cx_err = det.cx - frame_w / 2
        cy_err = det.cy - frame_h / 2

        # Yaw
        yaw_rate = max(
            -self.config.yaw_max_rate,
            min(self.config.yaw_max_rate, cx_err * self.config.yaw_p),
        )

        # Gimbal pitch — negative cy means object above center; pitch up.
        d_pitch = max(
            -self.config.pitch_max_deg_per_step,
            min(self.config.pitch_max_deg_per_step, -cy_err * self.config.pitch_p / 10),
        )
        self._gimbal_pitch = max(-90.0, min(30.0, self._gimbal_pitch + d_pitch))
        await self.drone.set_gimbal(self._gimbal_pitch)

        # Forward speed: maintain target bbox area
        area_ratio = det.area / max(1, frame_w * frame_h)
        area_err = self.config.target_bbox_area_ratio - area_ratio
        vx = max(
            -self.config.forward_max_speed,
            min(self.config.forward_max_speed, area_err * self.config.forward_p * 100),
        )
        await self.drone.set_velocity(vx, 0.0, 0.0, yaw_rate)
        return True

    def _pick_target(self, tracks: list[Track]) -> Optional[Track]:
        if self.config.target_track_id is not None:
            for t in tracks:
                if t.id == self.config.target_track_id:
                    return t
            return None
        # Otherwise: largest detection (closest)
        return max(tracks, key=lambda t: t.detection.area)
