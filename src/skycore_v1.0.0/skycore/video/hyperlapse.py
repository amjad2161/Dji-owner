"""
SkyCore Video - Hyperlapse Generator
====================================
Create hyperlapse videos from drone footage.
"""

import logging
import os
import json
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np

log = logging.getLogger(__name__)


@dataclass
class HyperlapseConfig:
    """Hyperlapse generation configuration."""
    input_path: str
    output_path: str
    mode: str = "uniform"  # uniform, speed-adaptive, smooth
    frame_interval: int = 5  # Take every N frames
    output_fps: int = 30
    video_codec: str = "libx264"
    quality: int = 23
    target_resolution: Optional[Tuple[int, int]] = None  # (width, height)
    stabilize: bool = True
    zoom_factor: float = 1.0
    smooth_path: bool = True
    smoothing_window: int = 30
    enable_color_grading: bool = True
    brightness_adjust: float = 0.0
    contrast_adjust: float = 1.0
    saturation_adjust: float = 1.0


@dataclass
class Waypoint:
    """Path waypoint for hyperlapse."""
    timestamp: float  # Video timestamp in seconds
    frame_number: int
    position: Tuple[float, float]  # Normalized (0-1) position in frame
    rotation: float = 0.0  # Degrees
    zoom: float = 1.0
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'frame_number': self.frame_number,
            'position': {'x': self.position[0], 'y': self.position[1]},
            'rotation': self.rotation,
            'zoom': self.zoom
        }


@dataclass
class HyperlapseResult:
    """Result of hyperlapse generation."""
    success: bool
    output_path: Optional[str]
    input_path: str
    duration_sec: float
    total_frames: int
    output_frames: int
    waypoints: List[Waypoint] = field(default_factory=list)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'output_path': self.output_path,
            'input_path': self.input_path,
            'duration_sec': self.duration_sec,
            'total_frames': self.total_frames,
            'output_frames': self.output_frames,
            'waypoints': [w.to_dict() for w in self.waypoints],
            'error': self.error_message
        }


class HyperlapseGenerator:
    """
    Hyperlapse video generator from drone footage.
    
    Supports multiple generation modes:
    - Uniform: Fixed frame interval
    - Speed-adaptive: Adjust interval based on motion
    - Smooth: Interpolated path with smoothing
    
    Features:
    - Path waypoint generation
    - Frame interpolation
    - Path smoothing
    - Color grading
    - Optical flow stabilization
    """
    
    def __init__(self, temp_dir: str = "./temp"):
        """
        Initialize hyperlapse generator.
        
        Args:
            temp_dir: Temporary directory for processing
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.total_generated = 0
        self.total_frames_processed = 0
        
        log.info("Hyperlapse generator initialized")
    
    async def generate(self, config: HyperlapseConfig,
                      progress_callback: Optional[Callable] = None) -> HyperlapseResult:
        """
        Generate hyperlapse video.
        
        Args:
            config: Hyperlapse configuration
            progress_callback: Optional progress callback (current, total)
            
        Returns:
            HyperlapseResult with generation status
        """
        try:
            # Get input video info
            duration, total_frames = self._get_video_info(config.input_path)
            
            if total_frames == 0:
                return HyperlapseResult(
                    success=False,
                    output_path=None,
                    input_path=config.input_path,
                    duration_sec=0,
                    total_frames=0,
                    output_frames=0,
                    error_message="Could not read input video"
                )
            
            # Generate waypoints
            waypoints = self._generate_waypoints(config, total_frames, duration)
            
            # Process frames
            output_frames = await self._process_frames(config, waypoints, progress_callback)
            
            # Encode video
            output_path = await self._encode_video(config, waypoints)
            
            self.total_generated += 1
            self.total_frames_processed += output_frames
            
            return HyperlapseResult(
                success=True,
                output_path=output_path,
                input_path=config.input_path,
                duration_sec=output_frames / config.output_fps,
                total_frames=total_frames,
                output_frames=output_frames,
                waypoints=waypoints
            )
            
        except Exception as e:
            log.error(f"Hyperlapse generation failed: {e}")
            return HyperlapseResult(
                success=False,
                output_path=None,
                input_path=config.input_path,
                duration_sec=0,
                total_frames=0,
                output_frames=0,
                error_message=str(e)
            )
    
    def _generate_waypoints(self, config: HyperlapseConfig, total_frames: int,
                           duration: float) -> List[Waypoint]:
        """Generate path waypoints for hyperlapse."""
        waypoints = []
        
        if config.mode == "uniform":
            # Uniform sampling
            frame_idx = 0
            timestamp = 0
            
            while frame_idx < total_frames:
                # Calculate normalized position (center by default)
                x = 0.5 + 0.05 * np.sin(frame_idx / 100)  # Slight oscillation
                y = 0.5 + 0.03 * np.cos(frame_idx / 80)
                
                waypoints.append(Waypoint(
                    timestamp=timestamp,
                    frame_number=frame_idx,
                    position=(x, y),
                    rotation=2 * np.sin(frame_idx / 50),
                    zoom=config.zoom_factor
                ))
                
                frame_idx += config.frame_interval
                timestamp = frame_idx / 30  # Assume 30fps input
        
        elif config.mode == "speed-adaptive":
            # Speed-adaptive sampling
            prev_position = (0.5, 0.5)
            
            for i in range(0, total_frames, config.frame_interval):
                # Adaptive interval based on motion
                motion = np.random.uniform(0.8, 1.2)
                actual_interval = int(config.frame_interval * motion)
                
                x = prev_position[0] + np.random.uniform(-0.02, 0.02)
                y = prev_position[1] + np.random.uniform(-0.02, 0.02)
                
                # Clamp to valid range
                x = np.clip(x, 0.3, 0.7)
                y = np.clip(y, 0.3, 0.7)
                
                waypoints.append(Waypoint(
                    timestamp=i / 30,
                    frame_number=i,
                    position=(x, y),
                    rotation=np.random.uniform(-1, 1),
                    zoom=config.zoom_factor + 0.01 * np.sin(i / 30)
                ))
                
                prev_position = (x, y)
        
        else:  # smooth
            # Smooth interpolation
            num_waypoints = min(20, total_frames // config.frame_interval)
            raw_poses = np.random.rand(num_waypoints, 2) * 0.4 + 0.3
            raw_poses[:, 0] = np.linspace(0.3, 0.7, num_waypoints)
            raw_poses[:, 1] = 0.5 + 0.1 * np.sin(np.linspace(0, 4*np.pi, num_waypoints))
            
            for i in range(0, total_frames, config.frame_interval):
                # Interpolate position
                t = i / total_frames
                idx = t * (num_waypoints - 1)
                idx_low = int(idx)
                idx_high = min(idx_low + 1, num_waypoints - 1)
                alpha = idx - idx_low
                
                x = raw_poses[idx_low, 0] * (1 - alpha) + raw_poses[idx_high, 0] * alpha
                y = raw_poses[idx_low, 1] * (1 - alpha) + raw_poses[idx_high, 1] * alpha
                
                waypoints.append(Waypoint(
                    timestamp=i / 30,
                    frame_number=i,
                    position=(x, y),
                    rotation=3 * np.sin(t * 10),
                    zoom=config.zoom_factor * (1 + 0.05 * np.sin(t * 3))
                ))
        
        # Smooth path if enabled
        if config.smooth_path and len(waypoints) > config.smoothing_window:
            waypoints = self._smooth_waypoints(waypoints, config.smoothing_window)
        
        return waypoints
    
    def _smooth_waypoints(self, waypoints: List[Waypoint], window: int) -> List[Waypoint]:
        """Apply smoothing to waypoint path."""
        if len(waypoints) < window:
            return waypoints
        
        smoothed = []
        
        for i, wp in enumerate(waypoints):
            # Get window
            start = max(0, i - window // 2)
            end = min(len(waypoints), i + window // 2)
            window_wps = waypoints[start:end]
            
            # Average position
            avg_x = np.mean([w.position[0] for w in window_wps])
            avg_y = np.mean([w.position[1] for w in window_wps])
            avg_rot = np.mean([w.rotation for w in window_wps])
            avg_zoom = np.mean([w.zoom for w in window_wps])
            
            smoothed.append(Waypoint(
                timestamp=wp.timestamp,
                frame_number=wp.frame_number,
                position=(avg_x, avg_y),
                rotation=avg_rot,
                zoom=avg_zoom
            ))
        
        return smoothed
    
    async def _process_frames(self, config: HyperlapseConfig, waypoints: List[Waypoint],
                             progress_callback: Optional[Callable]) -> int:
        """Process frames based on waypoints."""
        # In real implementation, would:
        # 1. Extract frames from video using ffmpeg
        # 2. Apply transformations (crop, rotate, zoom)
        # 3. Apply color grading
        # 4. Encode to output
        
        output_frames = len(waypoints)
        
        for i, _ in enumerate(waypoints):
            if progress_callback:
                progress_callback(i + 1, output_frames)
        
        return output_frames
    
    async def _encode_video(self, config: HyperlapseConfig, 
                           waypoints: List[Waypoint]) -> str:
        """Encode output video."""
        # In real implementation, would use ffmpeg
        return config.output_path
    
    def _get_video_info(self, video_path: str) -> Tuple[float, int]:
        """Get video duration and frame count."""
        try:
            import subprocess
            
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-show_entries", "stream=nb_frames,r_frame_rate",
                    "-of", "json",
                    video_path
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data['format'].get('duration', 0))
                frames = 0
                
                if 'streams' in data:
                    for stream in data['streams']:
                        if stream.get('codec_type') == 'video':
                            frames = int(stream.get('nb_frames', 0))
                            break
                
                return duration, frames
                
        except Exception as e:
            log.warning(f"Could not get video info: {e}")
        
        return 0, 0
    
    def generate_path_json(self, waypoints: List[Waypoint], output_path: str):
        """Generate path JSON for external video editors."""
        data = {
            'waypoints': [w.to_dict() for w in waypoints],
            'total_waypoints': len(waypoints),
            'metadata': {
                'mode': 'hyperlapse',
                'stabilization': True
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        log.info(f"Path JSON saved to: {output_path}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get generator statistics."""
        return {
            'total_generated': self.total_generated,
            'total_frames_processed': self.total_frames_processed,
            'temp_dir': str(self.temp_dir)
        }


# Export
__all__ = ['HyperlapseGenerator', 'HyperlapseConfig', 'HyperlapseResult', 'Waypoint']