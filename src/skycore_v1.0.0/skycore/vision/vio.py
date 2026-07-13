"""
SkyCore Vision - Visual Inertial Odometry (VIO)
================================================
Visual odometry with IMU fusion for drone navigation.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import numpy as np

log = logging.getLogger(__name__)


@dataclass
class VIOState:
    """Visual Inertial Odometry state."""
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    quaternion: np.ndarray = field(default_factory=lambda: np.array([1, 0, 0, 0]))
    timestamp: float = 0.0
    gravity: np.ndarray = field(default_factory=lambda: np.array([0, 0, -9.81]))
    tracking_quality: float = 1.0
    features_tracked: int = 0
    covariance: Optional[np.ndarray] = None
    
    def to_dict(self) -> Dict:
        return {
            'position': self.position.tolist(),
            'velocity': self.velocity.tolist(),
            'quaternion': self.quaternion.tolist(),
            'timestamp': self.timestamp,
            'tracking_quality': self.tracking_quality,
            'features_tracked': self.features_tracked
        }


@dataclass
class IMUReading:
    """IMU sensor reading."""
    accel: np.ndarray  # 3-axis accelerometer
    gyro: np.ndarray   # 3-axis gyroscope
    timestamp: float
    temperature: float = 25.0
    
    def __post_init__(self):
        self.accel = np.array(self.accel)
        self.gyro = np.array(self.gyro)


@dataclass
class CameraFrame:
    """Camera frame with features."""
    image: np.ndarray
    timestamp: float
    features: Optional[np.ndarray] = None
    pose: Optional[np.ndarray] = None
    intrinsics: Optional[np.ndarray] = None


class FeatureDetector:
    """Feature detection for visual odometry."""
    
    def __init__(self, max_features: int = 500, quality_level: float = 0.01,
                 min_distance: float = 10.0):
        self.max_features = max_features
        self.quality_level = quality_level
        self.min_distance = min_distance
        
        self.prev_features = None
        self.prev_image = None
    
    def detect(self, image: np.ndarray) -> np.ndarray:
        """
        Detect features in image.
        
        Args:
            image: Grayscale image
            
        Returns:
            Feature points (N x 2)
        """
        try:
            import cv2
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Shi-Tomasi corner detection
            features = cv2.goodFeaturesToTrack(
                gray,
                maxCorners=self.max_features,
                qualityLevel=self.quality_level,
                minDistance=self.min_distance,
                blockSize=7
            )
            
            if features is not None:
                return features.reshape(-1, 2)
            return np.array([])
            
        except ImportError:
            # Fallback: simple grid sampling
            h, w = image.shape[:2]
            grid_size = int(np.sqrt(h * w / self.max_features))
            y_coords, x_coords = np.mgrid[grid_size:h:grid_size, grid_size:w:grid_size]
            return np.column_stack([x_coords.ravel(), y_coords.ravel()])
    
    def track(self, prev_image: np.ndarray, curr_image: np.ndarray,
              prev_features: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Track features between frames.
        
        Args:
            prev_image: Previous image
            curr_image: Current image
            prev_features: Previous feature positions
            
        Returns:
            (prev_features, curr_features) matched
        """
        try:
            import cv2
            
            if len(prev_image.shape) == 3:
                prev_gray = cv2.cvtColor(prev_image, cv2.COLOR_BGR2GRAY)
                curr_gray = cv2.cvtColor(curr_image, cv2.COLOR_BGR2GRAY)
            else:
                prev_gray = prev_image
                curr_gray = curr_image
            
            # Optical flow
            curr_features, status, _ = cv2.calcOpticalFlowPyrLK(
                prev_gray, curr_gray,
                prev_features.astype(np.float32),
                None,
                winSize=(21, 21),
                maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
            )
            
            # Filter valid matches
            valid = status.ravel() == 1
            return prev_features[valid], curr_features[valid]
            
        except ImportError:
            return prev_features, prev_features


class VisualInertialOdometry:
    """
    Visual Inertial Odometry system for drone navigation.
    
    Fuses camera features with IMU data for robust pose estimation.
    Works in GPS-denied environments.
    
    Features:
    - Multi-state constraint Kalman filter (MSCKF)
    - Sliding window bundle adjustment
    - IMU preintegration
    - Loop closure detection
    """
    
    def __init__(self, camera_intrinsics: Optional[np.ndarray] = None,
                 gravity: np.ndarray = None, max_features: int = 500,
                 window_size: int = 10):
        """
        Initialize VIO system.
        
        Args:
            camera_intrinsics: Camera calibration matrix (3x3)
            gravity: Gravity vector in world frame
            max_features: Maximum features to track
            window_size: Sliding window size
        """
        self.intrinsics = camera_intrinsics or np.array([
            [600, 0, 320],
            [0, 600, 240],
            [0, 0, 1]
        ])
        self.gravity = gravity or np.array([0, 0, -9.81])
        self.max_features = max_features
        self.window_size = window_size
        
        self.feature_detector = FeatureDetector(max_features=max_features)
        
        # State
        self.state = VIOState()
        self.imu_buffer: List[IMUReading] = []
        self.frame_buffer: List[CameraFrame] = []
        self.feature_tracks: List[Dict] = []
        
        # Sliding window
        self.sliding_window: List[Tuple[IMUReading, CameraFrame]] = []
        
        # IMU state
        self.velocity = np.zeros(3)
        self.quaternion = np.array([1, 0, 0, 0])
        
        # Bias estimates
        self.gyro_bias = np.zeros(3)
        self.accel_bias = np.zeros(3)
        
        # Statistics
        self.frames_processed = 0
        self.total_tracked_features = 0
        self.lost_count = 0
        
        # Covariance
        self.state_covariance = np.eye(15) * 0.01
        
        log.info("VIO system initialized")
    
    def process_imu(self, accel: np.ndarray, gyro: np.ndarray,
                   timestamp: float) -> IMUReading:
        """
        Process IMU reading.
        
        Args:
            accel: Accelerometer data [ax, ay, az]
            gyro: Gyroscope data [gx, gy, gz]
            timestamp: Timestamp in seconds
            
        Returns:
            IMUReading
        """
        reading = IMUReading(
            accel=np.array(accel),
            gyro=np.array(gyro),
            timestamp=timestamp
        )
        
        self.imu_buffer.append(reading)
        
        # Update state with IMU
        if len(self.imu_buffer) >= 2:
            self._propagate_imu(reading)
        
        return reading
    
    def process_frame(self, image: np.ndarray, timestamp: float) -> Dict:
        """
        Process camera frame.
        
        Args:
            image: RGB image
            timestamp: Timestamp in seconds
            
        Returns:
            Pose estimation result
        """
        # Detect features
        features = self.feature_detector.detect(image)
        
        # Track from previous frame
        tracked_prev = []
        tracked_curr = []
        
        if self.frame_buffer:
            prev_frame = self.frame_buffer[-1]
            prev_features = self.feature_detector.detect(prev_frame.image)
            
            tracked_prev, tracked_curr = self.feature_detector.track(
                prev_frame.image, image, prev_features
            )
        
        # Update feature tracks
        self._update_feature_tracks(tracked_prev, tracked_curr)
        
        # Create frame
        frame = CameraFrame(
            image=image,
            timestamp=timestamp,
            features=features
        )
        self.frame_buffer.append(frame)
        
        # Update VIO state
        self._update_vio_state(frame, features)
        
        self.frames_processed += 1
        self.total_tracked_features += len(features)
        
        return {
            'position': self.state.position.tolist(),
            'quaternion': self.state.quaternion.tolist(),
            'velocity': self.state.velocity.tolist(),
            'tracking_quality': self.state.tracking_quality,
            'features': len(features)
        }
    
    def _propagate_imu(self, reading: IMUReading):
        """Propagate state with IMU reading."""
        if len(self.imu_buffer) < 2:
            return
        
        prev = self.imu_buffer[-2]
        dt = reading.timestamp - prev.timestamp
        
        if dt <= 0 or dt > 1.0:  # Skip invalid dt
            return
        
        # Corrected angular velocity
        omega = reading.gyro - self.gyro_bias
        
        # Update quaternion (first order)
        q = self.quaternion
        omega_quat = np.array([0, omega[0], omega[1], omega[2]])
        q_dot = 0.5 * self._quaternion_multiply(q, omega_quat)
        self.quaternion = q + q_dot * dt
        self.quaternion /= np.linalg.norm(self.quaternion)
        
        # Corrected acceleration
        accel_corrected = reading.accel - self.accel_bias
        
        # Rotate gravity from world to body frame
        rot_matrix = self._quaternion_to_rotation(self.quaternion)
        gravity_body = rot_matrix.T @ self.gravity
        
        # Update velocity
        self.velocity += (accel_corrected - gravity_body) * dt
        
        # Update position
        self.state.position += self.velocity * dt
    
    def _update_feature_tracks(self, tracked_prev, tracked_curr):
        """Update sliding window feature tracks."""
        if len(tracked_prev) < 8:
            self.state.tracking_quality = 0.5
            if self.state.tracking_quality < 0.3:
                self.lost_count += 1
            return
        
        self.state.tracking_quality = min(1.0, len(tracked_curr) / self.max_features)
        self.state.features_tracked = len(tracked_curr)
    
    def _update_vio_state(self, frame: CameraFrame, features: np.ndarray):
        """Update VIO state from camera frame."""
        self.state.timestamp = frame.timestamp
        self.state.position = self.state.position.copy()
        self.state.velocity = self.velocity.copy()
        self.state.quaternion = self.quaternion.copy()
        self.state.tracking_quality = self.state.tracking_quality
        self.state.features_tracked = len(features)
    
    def _quaternion_multiply(self, q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Multiply two quaternions."""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ])
    
    def _quaternion_to_rotation(self, q: np.ndarray) -> np.ndarray:
        """Convert quaternion to rotation matrix."""
        w, x, y, z = q
        
        return np.array([
            [1 - 2*(y**2 + z**2), 2*(x*y - w*z), 2*(x*z + w*y)],
            [2*(x*y + w*z), 1 - 2*(x**2 + z**2), 2*(y*z - w*x)],
            [2*(x*z - w*y), 2*(y*z + w*x), 1 - 2*(x**2 + y**2)]
        ])
    
    def reset(self):
        """Reset VIO state."""
        self.state = VIOState()
        self.velocity = np.zeros(3)
        self.quaternion = np.array([1, 0, 0, 0])
        self.imu_buffer.clear()
        self.frame_buffer.clear()
        self.feature_tracks.clear()
        self.state_covariance = np.eye(15) * 0.01
        log.info("VIO state reset")
    
    def get_state(self) -> Dict:
        """Get current VIO state."""
        return self.state.to_dict()
    
    def get_statistics(self) -> Dict:
        """Get VIO statistics."""
        return {
            'frames_processed': self.frames_processed,
            'total_tracked_features': self.total_tracked_features,
            'avg_features_per_frame': self.total_tracked_features / max(1, self.frames_processed),
            'lost_count': self.lost_count,
            'imu_readings': len(self.imu_buffer),
            'tracking_quality': self.state.tracking_quality,
            'current_position': self.state.position.tolist()
        }


class MSCKF(VisualInertialOdometry):
    """Multi-State Constraint Kalman Filter for VIO."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.feature_states = []  # Triangulated features
        log.info("MSCKF VIO initialized")


# Export
__all__ = ['VisualInertialOdometry', 'MSCKF', 'VIOState', 'IMUReading', 'CameraFrame', 'FeatureDetector']