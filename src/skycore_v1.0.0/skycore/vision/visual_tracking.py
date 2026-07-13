"""Visual tracking for following detected objects."""

import math
import asyncio
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass, field
from enum import Enum

import logging
import numpy as np

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class TrackState(Enum):
    """Visual track state."""
    SEARCHING = "searching"
    TRACKING = "tracking"
    LOST = "lost"
    LOCKED = "locked"


@dataclass
class TrackPoint:
    """Single tracked point history."""
    x: float
    y: float
    timestamp: float
    confidence: float = 1.0


class VisualTracker(LoggerMixin):
    """
    Visual tracker for following detected objects.
    
    Features:
    - Multi-object tracking
    - Motion prediction
    - Kalman filter smoothing
    - Lost target recovery
    """
    
    def __init__(self, max_history: int = 30, smooth_factor: float = 0.3):
        self.max_history = max_history
        self.smooth_factor = smooth_factor
        
        # Active tracks
        self.tracks: Dict[int, List[TrackPoint]] = {}
        self.track_states: Dict[int, TrackState] = {}
        self.last_positions: Dict[int, Tuple[float, float]] = {}
        
        # Track parameters
        self.lost_threshold_frames = 5
        self.min_confidence = 0.3
        self.prediction_enabled = True
        
        # Statistics
        self.total_tracks = 0
        self.active_tracks = 0
    
    async def update(self, detections: List[Tuple[int, float, float, float]]) -> Dict[int, Tuple[float, float]]:
        """
        Update tracker with new detections.
        
        Args:
            detections: List of (track_id, x, y, confidence)
        
        Returns:
            Dict of track_id -> smoothed (x, y)
        """
        smoothed = {}
        
        for track_id, x, y, confidence in detections:
            # Update track history
            if track_id not in self.tracks:
                self.tracks[track_id] = []
                self.track_states[track_id] = TrackState.TRACKING
            
            import time
            point = TrackPoint(x=x, y=y, timestamp=time.time(), confidence=confidence)
            self.tracks[track_id].append(point)
            
            # Limit history
            if len(self.tracks[track_id]) > self.max_history:
                self.tracks[track_id].pop(0)
            
            # Smooth position
            smoothed[track_id] = self._smooth_position(track_id)
            
            # Update state
            self.track_states[track_id] = TrackState.TRACKING if confidence > self.min_confidence else TrackState.LOST
        
        # Mark lost tracks
        self._update_lost_tracks()
        
        return smoothed
    
    def _smooth_position(self, track_id: int) -> Tuple[float, float]:
        """Apply exponential smoothing to position."""
        if track_id not in self.tracks or not self.tracks[track_id]:
            return (0.0, 0.0)
        
        history = self.tracks[track_id]
        
        if len(history) == 1:
            return (history[0].x, history[0].y)
        
        # Weighted average with recent emphasis
        weights = [self.smooth_factor ** (len(history) - i - 1) for i in range(len(history))]
        total_weight = sum(weights)
        
        x = sum(p.x * w for p, w in zip(history, weights)) / total_weight
        y = sum(p.y * w for p, w in zip(history, weights)) / total_weight
        
        return (x, y)
    
    def _update_lost_tracks(self):
        """Update states for tracks that haven't received updates."""
        import time
        current_time = time.time()
        
        for track_id, history in list(self.tracks.items()):
            if not history:
                continue
            
            last_update = history[-1].timestamp
            frames_since_update = int((current_time - last_update) * 10)  # Assume 10fps
            
            if frames_since_update > self.lost_threshold_frames:
                self.track_states[track_id] = TrackState.LOST
            else:
                self.track_states[track_id] = TrackState.TRACKING
    
    def predict_position(self, track_id: int, dt: float = 0.1) -> Optional[Tuple[float, float]]:
        """Predict future position based on motion."""
        if track_id not in self.tracks or len(self.tracks[track_id]) < 3:
            return None
        
        history = self.tracks[track_id]
        
        # Calculate velocity from recent points
        recent = history[-3:]
        
        if len(recent) < 2:
            return None
        
        vx = (recent[-1].x - recent[0].x) / (recent[-1].timestamp - recent[0].timestamp)
        vy = (recent[-1].y - recent[0].y) / (recent[-1].timestamp - recent[0].timestamp)
        
        # Predict future position
        current = history[-1]
        pred_x = current.x + vx * dt
        pred_y = current.y + vy * dt
        
        return (pred_x, pred_y)
    
    def get_track_state(self, track_id: int) -> TrackState:
        """Get current state of a track."""
        return self.track_states.get(track_id, TrackState.SEARCHING)
    
    def get_smoothed_position(self, track_id: int) -> Optional[Tuple[float, float]]:
        """Get smoothed position for a track."""
        if track_id not in self.tracks or not self.tracks[track_id]:
            return None
        return self._smooth_position(track_id)
    
    def get_trajectory(self, track_id: int, max_points: int = 30) -> List[Tuple[float, float]]:
        """Get trajectory history for a track."""
        if track_id not in self.tracks:
            return []
        
        history = self.tracks[track_id][-max_points:]
        return [(p.x, p.y) for p in history]
    
    def clear_track(self, track_id: int):
        """Clear a specific track."""
        if track_id in self.tracks:
            del self.tracks[track_id]
        if track_id in self.track_states:
            del self.track_states[track_id]
        if track_id in self.last_positions:
            del self.last_positions[track_id]
    
    def clear_all(self):
        """Clear all tracks."""
        self.tracks.clear()
        self.track_states.clear()
        self.last_positions.clear()
    
    def get_statistics(self) -> Dict:
        """Get tracker statistics."""
        return {
            'active_tracks': len(self.tracks),
            'tracking_count': sum(1 for s in self.track_states.values() if s == TrackState.TRACKING),
            'lost_count': sum(1 for s in self.track_states.values() if s == TrackState.LOST),
            'total_tracks': self.total_tracks
        }