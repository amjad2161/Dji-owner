"""
SkyCore Video - Gyroflow Integration
====================================
Wrapper for Gyroflow CLI for video stabilization.
"""

import asyncio
import logging
import os
import subprocess
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class GyroflowProject:
    """Gyroflow project settings."""
    video_path: str
    gyro_data_path: Optional[str] = None
    output_path: Optional[str] = None
    profile: str = "default"
    codec: str = "h264"
    quality: int = 23  # CRF value (lower = better quality)
    stabilization_strength: float = 1.0
    zoom: float = 1.0
    horizon_lock: float = 0.0
    lens_correction: bool = True
    optical_flow: bool = True
    motion_damping: float = 0.5
    horizon_damping: float = 0.5


@dataclass
class StabilizationResult:
    """Result of video stabilization."""
    success: bool
    output_path: Optional[str]
    input_path: str
    duration_sec: float
    processed_frames: int
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'output_path': self.output_path,
            'input_path': self.input_path,
            'duration_sec': self.duration_sec,
            'processed_frames': self.processed_frames,
            'error': self.error_message
        }


class GyroflowWrapper:
    """
    Gyroflow CLI wrapper for video stabilization.
    
    Gyroflow uses optical flow and IMU/gyroscope data for professional
    video stabilization. Supports 360° action cameras and drone footage.
    
    Features:
    - IMU-based stabilization
    - Horizon leveling
    - Lens correction
    - Motion damping
    - Multiple output formats
    """
    
    def __init__(self, gyroflow_path: str = "gyroflow", temp_dir: str = "./temp"):
        """
        Initialize Gyroflow wrapper.
        
        Args:
            gyroflow_path: Path to Gyroflow executable
            temp_dir: Temporary directory for processing
        """
        self.gyroflow_path = gyroflow_path
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.total_videos_stabilized = 0
        self.total_frames_processed = 0
        
        log.info(f"Gyroflow wrapper initialized with path: {gyroflow_path}")
    
    def is_available(self) -> bool:
        """Check if Gyroflow is available."""
        try:
            result = subprocess.run(
                [self.gyroflow_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    async def stabilize(self, project: GyroflowProject) -> StabilizationResult:
        """
        Stabilize video using Gyroflow.
        
        Args:
            project: Gyroflow project settings
            
        Returns:
            StabilizationResult with processing status
        """
        # Validate input
        if not os.path.exists(project.video_path):
            return StabilizationResult(
                success=False,
                output_path=None,
                input_path=project.video_path,
                duration_sec=0,
                processed_frames=0,
                error_message="Input video not found"
            )
        
        # Set output path
        if not project.output_path:
            video_name = Path(project.video_path).stem
            project.output_path = str(self.temp_dir / f"{video_name}_stabilized.mp4")
        
        # Run stabilization
        try:
            cmd = self._build_command(project)
            
            log.info(f"Starting Gyroflow stabilization: {cmd}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self.total_videos_stabilized += 1
                
                # Get video info
                duration, frames = self._get_video_info(project.output_path)
                self.total_frames_processed += frames
                
                log.info(f"Stabilization completed: {project.output_path}")
                
                return StabilizationResult(
                    success=True,
                    output_path=project.output_path,
                    input_path=project.video_path,
                    duration_sec=duration,
                    processed_frames=frames
                )
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                log.error(f"Gyroflow failed: {error_msg}")
                
                return StabilizationResult(
                    success=False,
                    output_path=None,
                    input_path=project.video_path,
                    duration_sec=0,
                    processed_frames=0,
                    error_message=error_msg
                )
                
        except Exception as e:
            log.error(f"Stabilization error: {e}")
            return StabilizationResult(
                success=False,
                output_path=None,
                input_path=project.video_path,
                duration_sec=0,
                processed_frames=0,
                error_message=str(e)
            )
    
    def _build_command(self, project: GyroflowProject) -> List[str]:
        """Build Gyroflow CLI command."""
        cmd = [
            self.gyroflow_path,
            "-i", project.video_path,
            "-o", project.output_path,
            "--output-codec", project.codec,
            "--quality", str(project.quality),
            "--stabilization-strength", str(project.stabilization_strength),
            "--zoom", str(project.zoom),
            "--horizon-lock", str(project.horizon_lock),
            "--motion-damping", str(project.motion_damping),
            "--horizon-damping", str(project.horizon_damping)
        ]
        
        if project.gyro_data_path:
            cmd.extend(["--gyro", project.gyro_data_path])
        
        if project.lens_correction:
            cmd.append("--lens-correction")
        
        if project.optical_flow:
            cmd.append("--optical-flow")
        
        return cmd
    
    def _get_video_info(self, video_path: str) -> Tuple[float, int]:
        """Get video duration and frame count using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-show_entries", "stream=nb_frames",
                    "-of", "json",
                    video_path
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data['format'].get('duration', 0))
                frames = int(data['streams'][0].get('nb_frames', 0)) if 'streams' in data else 0
                return duration, frames
                
        except Exception as e:
            log.warning(f"Could not get video info: {e}")
        
        return 0, 0
    
    def create_project_file(self, project: GyroflowProject, path: str):
        """Create Gyroflow .gyroflow project file."""
        project_data = {
            "version": "1.0",
            "input": {
                "video": project.video_path,
                "gyro": project.gyro_data_path
            },
            "output": {
                "codec": project.codec,
                "quality": project.quality,
                "path": project.output_path
            },
            "stabilization": {
                "strength": project.stabilization_strength,
                "zoom": project.zoom,
                "horizon_lock": project.horizon_lock,
                "motion_damping": project.motion_damping,
                "horizon_damping": project.horizon_damping
            },
            "lens_correction": {
                "enabled": project.lens_correction
            },
            "optical_flow": {
                "enabled": project.optical_flow
            }
        }
        
        with open(path, 'w') as f:
            json.dump(project_data, f, indent=2)
        
        log.info(f"Gyroflow project file created: {path}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get wrapper statistics."""
        return {
            'total_videos_stabilized': self.total_videos_stabilized,
            'total_frames_processed': self.total_frames_processed,
            'gyroflow_available': self.is_available(),
            'temp_dir': str(self.temp_dir)
        }


class BatchGyroflow:
    """Batch process multiple videos with Gyroflow."""
    
    def __init__(self, gyroflow_wrapper: GyroflowWrapper, max_concurrent: int = 2):
        self.wrapper = gyroflow_wrapper
        self.max_concurrent = max_concurrent
        self._processing = False
        self._results: List[StabilizationResult] = []
    
    async def process_batch(self, projects: List[GyroflowProject],
                           progress_callback: Optional[callable] = None) -> List[StabilizationResult]:
        """
        Process multiple videos in batch.
        
        Args:
            projects: List of Gyroflow projects
            progress_callback: Optional progress callback
            
        Returns:
            List of StabilizationResults
        """
        self._results = []
        self._processing = True
        
        tasks = []
        for project in projects:
            task = asyncio.create_task(self.wrapper.stabilize(project))
            tasks.append((project, task))
        
        completed = 0
        total = len(tasks)
        
        for project, task in tasks:
            try:
                result = await task
                self._results.append(result)
                
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
                    
            except Exception as e:
                log.error(f"Batch processing error: {e}")
                self._results.append(StabilizationResult(
                    success=False,
                    output_path=None,
                    input_path=project.video_path,
                    duration_sec=0,
                    processed_frames=0,
                    error_message=str(e)
                ))
        
        self._processing = False
        return self._results
    
    def get_successful(self) -> List[StabilizationResult]:
        """Get all successful stabilizations."""
        return [r for r in self._results if r.success]
    
    def get_failed(self) -> List[StabilizationResult]:
        """Get all failed stabilizations."""
        return [r for r in self._results if not r.success]


# Export
__all__ = ['GyroflowWrapper', 'GyroflowProject', 'StabilizationResult', 'BatchGyroflow']