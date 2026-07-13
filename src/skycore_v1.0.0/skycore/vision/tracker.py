"""
SkyCore Vision - Object Tracker
================================
Multi-object tracking using BoT-SORT and other algorithms.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np

log = logging.getLogger(__name__)


@dataclass
class Track:
    """Single object track."""
    track_id: int
    class_name: str
    class_id: int
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    center: Tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))
    velocity: Tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))
    age: int = 0  # Frames since last detection
    hits: int = 0  # Number of detections
    timestamp: float = field(default_factory=time.time)
    features: np.ndarray = field(default_factory=lambda: np.zeros(512))
    
    def __post_init__(self):
        x1, y1, x2, y2 = self.bbox
        self.center = ((x1 + x2) / 2, (y1 + y2) / 2)
    
    def to_dict(self) -> Dict:
        return {
            'track_id': self.track_id,
            'class_name': self.class_name,
            'bbox': self.bbox,
            'confidence': self.confidence,
            'center': self.center,
            'velocity': self.velocity,
            'age': self.age,
            'hits': self.hits
        }


@dataclass
class TrackResult:
    """Tracking result for a frame."""
    tracks: List[Track]
    frame_id: int = 0
    timestamp: float = field(default_factory=time.time)
    
    def get_by_class(self, class_name: str) -> List[Track]:
        return [t for t in self.tracks if class_name.lower() in t.class_name.lower()]
    
    def get_by_id(self, track_id: int) -> Optional[Track]:
        for t in self.tracks:
            if t.track_id == track_id:
                return t
        return None
    
    @property
    def person_tracks(self) -> List[Track]:
        return self.get_by_class('person')
    
    @property
    def vehicle_tracks(self) -> List[Track]:
        return self.get_by_class(['car', 'truck', 'bus', 'vehicle'])


class BoTSortTracker:
    """
    BoT-SORT (Bot Simple Online and Realtime Tracking) implementation.
    
    Multi-object tracker optimized for real-time tracking with re-ID capability.
    
    Features:
    - ByteTrack-style association
    - ReID embedding for track continuity
    - Motion prediction using Kalman filter
    - Age-based track management
    """
    
    def __init__(self, track_thresh: float = 0.5, track_buffer: int = 30,
                 match_thresh: float = 0.8, track_age: int = 30,
                 min_hits: int = 3, max_time_lost: int = 30):
        """
        Initialize BoT-SORT tracker.
        
        Args:
            track_thresh: Detection confidence threshold for tracking
            track_buffer: Buffer for keeping lost tracks
            match_thresh: Matching threshold for IoU
            track_age: Maximum age for tracks
            min_hits: Minimum detections to confirm track
            max_time_lost: Maximum frames to keep lost track
        """
        self.track_thresh = track_thresh
        self.track_buffer = track_buffer
        self.match_thresh = match_thresh
        self.track_age = track_age
        self.min_hits = min_hits
        self.max_time_lost = max_time_lost
        
        self.tracks: List[Track] = []
        self.next_id = 1
        self.frame_count = 0
        
        # Kalman filter for motion prediction
        self.kalman_filters: Dict[int, 'KalmanBoxTracker'] = {}
        
        # Feature extractor (placeholder - would use actual re-ID model)
        self.feature_dim = 512
        
        # Track statistics
        self.total_tracks = 0
        self.total_associations = 0
        
        log.info("BoT-SORT tracker initialized")
    
    def update(self, detections: List[Tuple], frame: Optional[np.ndarray] = None) -> List[Track]:
        """
        Update tracker with new detections.
        
        Args:
            detections: List of (bbox, confidence, class_id, class_name) tuples
            frame: Optional frame for feature extraction
            
        Returns:
            List of active tracks
        """
        self.frame_count += 1
        
        # Extract detection data
        dets = []
        for det in detections:
            if len(det) == 4:
                bbox, conf, cls_id, cls_name = det
                dets.append({
                    'bbox': bbox,
                    'confidence': conf,
                    'class_id': cls_id,
                    'class_name': cls_name
                })
        
        # Update Kalman filters and predict
        for track in self.tracks:
            if track.track_id in self.kalman_filters:
                kf = self.kalman_filters[track.track_id]
                pred = kf.predict()
                # Update velocity
                track.velocity = (pred[0] - track.center[0], pred[1] - track.center[1])
        
        # Association
        matched, unmatched_dets, unmatched_tracks = self._associate(dets)
        
        # Update matched tracks
        for det_idx, track_idx in matched:
            track = self.tracks[track_idx]
            det = dets[det_idx]
            
            track.bbox = det['bbox']
            track.confidence = det['confidence']
            track.age = 0
            track.hits += 1
            
            x1, y1, x2, y2 = det['bbox']
            track.center = ((x1 + x2) / 2, (y1 + y2) / 2)
            
            # Update Kalman filter
            if track.track_id in self.kalman_filters:
                self.kalman_filters[track.track_id].update(track.center)
        
        # Age unmatched tracks
        for idx in unmatched_tracks:
            self.tracks[idx].age += 1
        
        # Create new tracks from unmatched detections
        for det_idx in unmatched_dets:
            det = dets[det_idx]
            
            if det['confidence'] < self.track_thresh:
                continue
            
            new_track = Track(
                track_id=self.next_id,
                class_name=det['class_name'],
                class_id=det['class_id'],
                bbox=det['bbox'],
                confidence=det['confidence'],
                hits=1,
                age=0
            )
            
            self.tracks.append(new_track)
            self.kalman_filters[self.next_id] = KalmanBoxTracker(new_track.center)
            self.next_id += 1
            self.total_tracks += 1
        
        # Remove old tracks
        self.tracks = [t for t in self.tracks if t.age < self.max_time_lost]
        
        # Return confirmed tracks
        return [t for t in self.tracks if t.hits >= self.min_hits]
    
    def _associate(self, detections: List[Dict]) -> Tuple[List, List, List]:
        """Associate detections with tracks using IoU and ByteTrack."""
        if not self.tracks:
            return [], list(range(len(detections))), []
        
        # Compute IoU matrix
        iou_matrix = self._compute_iou_matrix(detections, self.tracks)
        
        # First association (high confidence)
        high_mask = np.array([d['confidence'] > 0.5 for d in detections])
        high_inds = np.where(high_mask)[0]
        
        matched = []
        unmatched_detections = []
        unmatched_tracks = list(range(len(self.tracks)))
        
        # Match high confidence detections
        for det_idx in high_inds:
            best_iou = self.match_thresh
            best_track = -1
            
            for track_idx in unmatched_tracks:
                iou = iou_matrix[det_idx, track_idx]
                if iou > best_iou:
                    best_iou = iou
                    best_track = track_idx
            
            if best_track >= 0:
                matched.append((det_idx, best_track))
                unmatched_tracks.remove(best_track)
            else:
                unmatched_detections.append(det_idx)
        
        # Second association (all detections)
        if unmatched_detections and unmatched_tracks:
            for det_idx in unmatched_detections:
                best_iou = 0.3
                best_track = -1
                
                for track_idx in unmatched_tracks:
                    iou = iou_matrix[det_idx, track_idx]
                    if iou > best_iou:
                        best_iou = iou
                        best_track = track_idx
                
                if best_track >= 0:
                    matched.append((det_idx, best_track))
                    unmatched_tracks.remove(best_track)
        
        unmatched_detections = [i for i in range(len(detections)) 
                                if i not in [m[0] for m in matched]]
        
        return matched, unmatched_detections, unmatched_tracks
    
    def _compute_iou_matrix(self, detections: List[Dict], tracks: List[Track]) -> np.ndarray:
        """Compute IoU matrix between detections and tracks."""
        n_dets = len(detections)
        n_tracks = len(tracks)
        
        iou_matrix = np.zeros((n_dets, n_tracks))
        
        for i, det in enumerate(detections):
            det_bbox = det['bbox']
            
            for j, track in enumerate(tracks):
                track_bbox = track.bbox
                
                # Compute IoU
                x1 = max(det_bbox[0], track_bbox[0])
                y1 = max(det_bbox[1], track_bbox[1])
                x2 = min(det_bbox[2], track_bbox[2])
                y2 = min(det_bbox[3], track_bbox[3])
                
                inter = max(0, x2 - x1) * max(0, y2 - y1)
                area_det = (det_bbox[2] - det_bbox[0]) * (det_bbox[3] - det_bbox[1])
                area_track = (track_bbox[2] - track_bbox[0]) * (track_bbox[3] - track_bbox[1])
                union = area_det + area_track - inter
                
                iou_matrix[i, j] = inter / union if union > 0 else 0
        
        return iou_matrix
    
    def reset(self):
        """Reset tracker state."""
        self.tracks = []
        self.kalman_filters = {}
        self.next_id = 1
        self.frame_count = 0
        log.info("Tracker reset")


class KalmanBoxTracker:
    """Kalman filter for bounding box tracking."""
    
    count = 0
    
    def __init__(self, center):
        """
        Initialize Kalman filter for box tracking.
        
        Args:
            center: Initial center position (x, y)
        """
        self.kf = KalmanFilter(dim_x=7, dim_z=4)
        
        # State: [x, y, w, h, vx, vy, vw]
        self.kf.F = np.array([
            [1, 0, 0, 0, 1, 0, 0],
            [0, 1, 0, 0, 0, 1, 0],
            [0, 0, 1, 0, 0, 0, 1],
            [0, 0, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 1]
        ])
        
        self.kf.H = np.array([
            [1, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0]
        ])
        
        self.kf.R[2:, 2:] *= 10
        self.kf.P[4:, 4:] *= 1000
        self.kf.P *= 10
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[4:, 4:] *= 0.01
        
        self.kf.x[:4] = self._convert_bbox_to_z(center, 100, 100)
        
        self.time_since_update = 0
        self.id = KalmanBoxTracker.count
        KalmanBoxTracker.count += 1
        self.history = []
        self.hits = 0
        self.hit_streak = 0
        self.age = 0
    
    def update(self, bbox):
        """Update with new detection."""
        self.time_since_update = 0
        self.history = []
        self.hits += 1
        self.hit_streak += 1
        self.kf.update(self._convert_bbox_to_z(bbox, 0, 0))
    
    def predict(self):
        """Predict next state."""
        if (self.kf.x[6] + self.kf.x[2]) <= 0:
            self.kf.x[6] *= 0.0
        
        self.kf.predict()
        self.age += 1
        
        if self.time_since_update > 0:
            self.hit_streak = 0
        
        self.time_since_update += 1
        self.history.append(self._convert_x_to_bbox(self.kf.x))
        
        return self.history[-1]
    
    def get_state(self):
        """Get current state."""
        return self._convert_x_to_bbox(self.kf.x)
    
    def _convert_bbox_to_z(self, center, w, h):
        """Convert bbox to state vector."""
        return np.array([center[0], center[1], w, h, 0, 0, 0])
    
    def _convert_x_to_bbox(self, x):
        """Convert state vector to bbox."""
        w = x[2]
        h = x[3]
        x_center = x[0]
        y_center = x[1]
        
        return [x_center - w/2, y_center - h/2, x_center + w/2, y_center + h/2]


class KalmanFilter:
    """Simple Kalman filter implementation."""
    
    def __init__(self, dim_x, dim_z):
        self.dim_x = dim_x
        self.dim_z = dim_z
        
        self.x = np.zeros((dim_x, 1))
        self.P = np.eye(dim_x)
        self.Q = np.eye(dim_x) * 0.001
        self.R = np.eye(dim_z) * 1
        self.H = np.eye(dim_z, dim_x)
        self.F = np.eye(dim_x)
        self.K = np.zeros((dim_x, dim_z))
        
        self.Predicted = np.zeros((dim_x, dim_x))
        self.y = np.zeros((dim_z, 1))
    
    def predict(self):
        """Predict step."""
        self.x = self.F @ self.x
        self.Predicted = self.F @ self.P @ self.F.T + self.Q
        self.P = self.Predicted
    
    def update(self, z):
        """Update step."""
        z = np.array(z).reshape(-1, 1)
        self.y = z - self.H @ self.x
        
        S = self.H @ self.P @ self.H.T + self.R
        self.K = self.P @ self.H.T @ np.linalg.inv(S)
        
        self.x = self.x + self.K @ self.y
        self.P = (np.eye(self.dim_x) - self.K @ self.H) @ self.P


class DeepSortTracker(BoTSortTracker):
    """DeepSORT-style tracker with re-ID features."""
    
    def __init__(self, reid_model: str = "osnet", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reid_model = reid_model
        self.feature_history: Dict[int, List[np.ndarray]] = defaultdict(list)
        log.info(f"DeepSORT tracker with {reid_model} initialized")
    
    def extract_features(self, crops: List[np.ndarray]) -> List[np.ndarray]:
        """Extract re-ID features from image crops."""
        # Placeholder - would use actual re-ID model
        return [np.random.randn(512) for _ in crops]
    
    def cosine_distance(self, feat1: np.ndarray, feat2: np.ndarray) -> float:
        """Compute cosine distance between features."""
        return 1 - np.dot(feat1, feat2) / (np.linalg.norm(feat1) * np.linalg.norm(feat2))


# Export
__all__ = ['BoTSortTracker', 'DeepSortTracker', 'Track', 'TrackResult', 'KalmanBoxTracker', 'KalmanFilter']