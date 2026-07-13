"""
SkyCore Streaming - Video Streaming Module
RTMP, HLS, and RTSP streaming capabilities
"""

import asyncio
import subprocess
import os
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)


class StreamProtocol(Enum):
    """Supported streaming protocols"""
    RTMP = "rtmp"
    HLS = "hls"
    RTSP = "rtsp"
    WEBM = "webm"


@dataclass
class StreamConfig:
    """Stream configuration"""
    protocol: StreamProtocol
    input_url: str
    output_url: str
    resolution: str = "1920x1080"
    bitrate: str = "4M"
    fps: int = 30
    codec: str = "libx264"
    audio: bool = True
    audio_codec: str = "aac"
    audio_bitrate: str = "128k"


class Streamer:
    """Main video streamer using FFmpeg"""
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.streaming = False
        self.bytes_sent = 0
        self.start_time = None
        
        logger.info(f"Streamer initialized: {config.protocol.value} → {config.output_url}")
    
    async def start(self) -> bool:
        """Start streaming"""
        if self.streaming:
            logger.warning("Stream already running")
            return False
        
        try:
            cmd = self._build_ffmpeg_command()
            
            logger.info(f"Starting stream with command: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL
            )
            
            self.streaming = True
            self.start_time = time.time()
            
            # Start monitoring task
            asyncio.create_task(self._monitor_stream())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start stream: {e}")
            return False
    
    async def stop(self):
        """Stop streaming"""
        if not self.streaming:
            return
        
        self.streaming = False
        
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            
            self.process = None
        
        duration = time.time() - self.start_time if self.start_time else 0
        logger.info(f"Stream stopped after {duration:.1f}s")
    
    def _build_ffmpeg_command(self) -> List[str]:
        """Build FFmpeg command based on protocol"""
        cmd = ['ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=3600:size=1920x1080:rate=30']
        
        # Video codec
        if self.config.codec == 'libx264':
            cmd.extend(['-c:v', 'libx264', '-preset', 'fast', '-b:v', self.config.bitrate])
        elif self.config.codec == 'libx265':
            cmd.extend(['-c:v', 'libx265', '-preset', 'fast', '-b:v', self.config.bitrate])
        elif self.config.codec == 'copy':
            cmd.extend(['-c:v', 'copy'])
        
        # Resolution and FPS
        cmd.extend(['-s', self.config.resolution, '-r', str(self.config.fps)])
        
        # Audio
        if self.config.audio:
            cmd.extend(['-c:a', self.config.audio_codec, '-b:a', self.config.audio_bitrate])
        else:
            cmd.append('-an')
        
        # Protocol-specific output
        if self.config.protocol == StreamProtocol.RTMP:
            cmd.extend(['-f', 'flv', self.config.output_url])
        elif self.config.protocol == StreamProtocol.HLS:
            cmd.extend(['-f', 'hls', '-hls_time', '2', '-hls_list_size', '10', 
                       '-hls_segment_filename', 'segment_%03d.ts', self.config.output_url])
        elif self.config.protocol == StreamProtocol.RTSP:
            cmd.extend(['-f', 'rtsp', '-rtsp_transport', 'tcp', self.config.output_url])
        
        # Non-blocking input
        cmd.append('-re')
        
        return cmd
    
    async def _monitor_stream(self):
        """Monitor stream health"""
        while self.streaming and self.process:
            if self.process.poll() is not None:
                logger.error("Stream process died unexpectedly")
                self.streaming = False
                break
            
            await asyncio.sleep(5)
            
            # Calculate stats
            if self.start_time:
                duration = time.time() - self.start_time
                logger.debug(f"Stream running for {duration:.0f}s...")
    
    def get_stats(self) -> Dict:
        """Get streaming statistics"""
        return {
            'streaming': self.streaming,
            'protocol': self.config.protocol.value,
            'output_url': self.config.output_url,
            'duration_s': time.time() - self.start_time if self.start_time else 0,
            'uptime_formatted': self._format_uptime()
        }
    
    def _format_uptime(self) -> str:
        """Format uptime as HH:MM:SS"""
        if not self.start_time:
            return "00:00:00"
        
        seconds = int(time.time() - self.start_time)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class HLSProxy:
    """HLS proxy for video streaming through server"""
    
    def __init__(self, listen_port: int = 8080):
        self.listen_port = listen_port
        self.server = None
        self.active = False
        
        logger.info(f"HLS Proxy initialized on port {listen_port}")
    
    async def start(self):
        """Start HLS proxy server"""
        if self.active:
            return
        
        # Simple HTTP server for HLS
        self.active = True
        logger.info("HLS Proxy started")
        
        # In production, use aiohttp or fastapi for actual server
        while self.active:
            await asyncio.sleep(1)
    
    async def stop(self):
        """Stop HLS proxy"""
        self.active = False
        logger.info("HLS Proxy stopped")
    
    async def serve_segment(self, segment_path: str) -> bytes:
        """Serve HLS segment file"""
        try:
            with open(segment_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to serve segment: {e}")
            return b''


class StreamManager:
    """Manage multiple streams"""
    
    def __init__(self):
        self.streams: Dict[str, Streamer] = {}
        self.hls_proxies: Dict[str, HLSProxy] = {}
        
        logger.info("Stream manager initialized")
    
    async def create_stream(self, name: str, config: StreamConfig) -> Streamer:
        """Create new stream"""
        streamer = Streamer(config)
        self.streams[name] = streamer
        
        logger.info(f"Created stream: {name}")
        return streamer
    
    async def start_stream(self, name: str) -> bool:
        """Start specific stream"""
        if name not in self.streams:
            logger.error(f"Stream not found: {name}")
            return False
        
        return await self.streams[name].start()
    
    async def stop_stream(self, name: str):
        """Stop specific stream"""
        if name in self.streams:
            await self.streams[name].stop()
            del self.streams[name]
            logger.info(f"Stopped stream: {name}")
    
    async def stop_all(self):
        """Stop all streams"""
        for name in list(self.streams.keys()):
            await self.stop_stream(name)
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """Get stats for all streams"""
        return {name: streamer.get_stats() for name, streamer in self.streams.items()}


def create_rtmp_stream(output_url: str, resolution: str = "1920x1080") -> StreamConfig:
    """Create RTMP stream configuration"""
    return StreamConfig(
        protocol=StreamProtocol.RTMP,
        input_url="testsrc",
        output_url=output_url,
        resolution=resolution,
        bitrate="4M",
        fps=30,
        codec="libx264",
        audio=True
    )


def create_hls_stream(output_path: str, resolution: str = "1920x1080") -> StreamConfig:
    """Create HLS stream configuration"""
    return StreamConfig(
        protocol=StreamProtocol.HLS,
        input_url="testsrc",
        output_url=output_path,
        resolution=resolution,
        bitrate="4M",
        fps=30,
        codec="libx264",
        audio=True
    )


def create_stream_manager() -> StreamManager:
    """Factory function"""
    return StreamManager()