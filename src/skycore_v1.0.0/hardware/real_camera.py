"""
SkyCore Real Camera Driver
Real camera interface using OpenCV
"""

import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from threading import Thread, Lock
from queue import Queue
import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealCamera:
    """
    Real camera driver using OpenCV
    Supports USB cameras, IP cameras, and video files
    """
    
    def __init__(
        self,
        source: int = 0,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30
    ):
        if not HAS_CV2:
            raise RuntimeError("OpenCV required: pip install opencv-python")
            
        self.source = source
        self.width = width
        self.height = height
        self.fps = fps
        
        self.capture = None
        self.running = False
        self.thread = None
        
        self.frame_queue: Queue = Queue(maxsize=5)
        self.lock = Lock()
        
        # Frame statistics
        self.frame_count = 0
        self.last_frame_time = 0
        self.dropped_frames = 0
        
        # Current frame
        self.current_frame = None
        self.current_frame_rgb = None
        
        # Camera info
        self.camera_name = "Unknown"
        self.supported_resolutions = []
        
    def open(self, source: Any = None) -> bool:
        """
        Open camera
        
        Args:
            source: Camera index (0,1,2...), URL, or file path
            
        Returns:
            True if opened successfully
        """
        if source is not None:
            self.source = source
            
        try:
            logger.info(f"Opening camera: {self.source}")
            
            # Try as video source
            if isinstance(self.source, str):
                self.capture = cv2.VideoCapture(self.source)
            else:
                self.capture = cv2.VideoCapture(int(self.source))
                
            if not self.capture.isOpened():
                logger.error(f"Failed to open camera: {self.source}")
                return False
                
            # Configure camera
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.capture.set(cv2.CAP_PROP_FPS, self.fps)
            
            # Try to set format
            self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            
            # Verify settings
            actual_width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.capture.get(cv2.CAP_PROP_FPS))
            
            self.width = actual_width
            self.height = actual_height
            self.fps = actual_fps
            
            logger.info(f"Camera opened: {actual_width}x{actual_height} @ {actual_fps} FPS")
            
            self.running = True
            self.thread = Thread(target=self._capture_loop, daemon=True)
            self.thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Camera open failed: {e}")
            return False
            
    def close(self):
        """Close camera"""
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=2)
            
        if self.capture:
            self.capture.release()
            self.capture = None
            
        logger.info("Camera closed")
        
    def is_open(self) -> bool:
        """Check if camera is open"""
        return self.capture is not None and self.capture.isOpened()
        
    def _capture_loop(self):
        """Background capture loop"""
        while self.running:
            try:
                if self.capture and self.capture.isOpened():
                    ret, frame = self.capture.read()
                    
                    if ret:
                        with self.lock:
                            self.current_frame = frame.copy()
                            self.current_frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            
                        self.frame_count += 1
                        self.last_frame_time = time.time()
                        
                        # Put in queue (drop if full)
                        if self.frame_queue.full():
                            self.dropped_frames += 1
                            try:
                                self.frame_queue.get_nowait()
                            except:
                                pass
                                
                        self.frame_queue.put(frame.copy())
                    else:
                        logger.warning("Camera frame grab failed")
                        time.sleep(0.1)
                        
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Capture error: {e}")
                time.sleep(0.1)
                
    def read(self) -> Optional[np.ndarray]:
        """
        Read current frame
        
        Returns:
            Frame as numpy array or None
        """
        with self.lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        return None
        
    def read_rgb(self) -> Optional[np.ndarray]:
        """Read current frame as RGB"""
        with self.lock:
            if self.current_frame_rgb is not None:
                return self.current_frame_rgb.copy()
        return None
        
    def get_frame_queue(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """Get frame from queue"""
        try:
            return self.frame_queue.get(timeout=timeout)
        except:
            return None
            
    def set_brightness(self, value: int):
        """Set brightness (0-255)"""
        if self.capture:
            self.capture.set(cv2.CAP_PROP_BRIGHTNESS, value)
            
    def set_contrast(self, value: int):
        """Set contrast (0-255)"""
        if self.capture:
            self.capture.set(cv2.CAP_PROP_CONTRAST, value)
            
    def set_exposure(self, value: int):
        """Set exposure (0-100)"""
        if self.capture:
            self.capture.set(cv2.CAP_PROP_EXPOSURE, value)
            
    def set_white_balance(self, value: int):
        """Set white balance temperature"""
        if self.capture:
            self.capture.set(cv2.CAP_PROP_WHITE_BALANCE_BLUE_U, value)
            
    def auto_exposure(self, enable: bool = True):
        """Enable/disable auto exposure"""
        if self.capture:
            # Most webcams don't support this directly
            pass
            
    def get_info(self) -> Dict:
        """Get camera information"""
        return {
            'source': self.source,
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'open': self.is_open(),
            'frame_count': self.frame_count,
            'dropped_frames': self.dropped_frames
        }


class VideoRecorder:
    """
    Video recording from camera
    """
    
    def __init__(
        self,
        camera: RealCamera,
        output_file: str,
        codec: str = 'MJPG'
    ):
        self.camera = camera
        self.output_file = output_file
        self.codec = codec
        
        self.writer = None
        self.running = False
        self.thread = None
        
        self.frames_recorded = 0
        
    def start(self) -> bool:
        """Start recording"""
        if not self.camera.is_open():
            logger.error("Camera not open")
            return False
            
        try:
            fourcc = cv2.VideoWriter_fourcc(*self.codec)
            self.writer = cv2.VideoWriter(
                self.output_file,
                fourcc,
                self.camera.fps,
                (self.camera.width, self.camera.height)
            )
            
            if not self.writer.isOpened():
                logger.error("Failed to create video writer")
                return False
                
            self.running = True
            self.thread = Thread(target=self._record_loop, daemon=True)
            self.thread.start()
            
            logger.info(f"Recording started: {self.output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Start recording failed: {e}")
            return False
            
    def stop(self):
        """Stop recording"""
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=5)
            
        if self.writer:
            self.writer.release()
            self.writer = None
            
        logger.info(f"Recording stopped: {self.frames_recorded} frames")
        
    def _record_loop(self):
        """Record loop"""
        while self.running:
            frame = self.camera.get_frame_queue(timeout=1.0)
            
            if frame is not None:
                self.writer.write(frame)
                self.frames_recorded += 1


class CameraCalibration:
    """
    Camera calibration for undistortion
    """
    
    def __init__(self):
        self.camera_matrix = None
        self.dist_coeffs = None
        self.new_camera_matrix = None
        self.roi = None
        
        self.calibrated = False
        
    def load_calibration(self, file_path: str):
        """Load calibration from file"""
        try:
            fs = cv2.FileStorage(file_path, cv2.FILE_STORAGE_READ)
            
            self.camera_matrix = fs.getNode('camera_matrix').mat()
            self.dist_coeffs = fs.getNode('dist_coeffs').mat()
            self.new_camera_matrix = fs.getNode('new_camera_matrix').mat()
            self.roi = fs.getNode('roi').mat()
            
            fs.release()
            
            self.calibrated = True
            logger.info(f"Calibration loaded from {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to load calibration: {e}")
            
    def undistort(self, frame: np.ndarray) -> np.ndarray:
        """Undistort image"""
        if not self.calibrated:
            return frame
            
        return cv2.undistort(
            frame,
            self.camera_matrix,
            self.dist_coeffs,
            None,
            self.new_camera_matrix
        )
        
    def undistort_points(self, points: np.ndarray) -> np.ndarray:
        """Undistort points"""
        if not self.calibrated or self.camera_matrix is None:
            return points
            
        return cv2.undistortPoints(
            points,
            self.camera_matrix,
            self.dist_coeffs,
            None,
            self.new_camera_matrix
        )


# Example usage
if __name__ == "__main__":
    print("Starting camera test...")
    
    # List available cameras
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"Camera {i}: {frame.shape}")
        cap.release()
        
    # Open camera
    camera = RealCamera(0, width=1280, height=720, fps=30)
    
    if camera.open():
        print("Camera opened")
        
        # Get some frames
        for _ in range(10):
            frame = camera.read()
            if frame is not None:
                print(f"Frame: {frame.shape}")
                
            time.sleep(0.1)
            
        camera.close()
    else:
        print("Failed to open camera")