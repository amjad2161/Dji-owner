"""RTMP streamer. Pushes a video stream to YouTube / Twitch / Facebook / custom RTMP.

Reuses the LocalRecorder pipeline but with an RTMP destination URL.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Optional

log = logging.getLogger(__name__)


class RtmpStreamer:
    def __init__(
        self,
        rtmp_url: str,
        width: int,
        height: int,
        fps: int = 30,
        bitrate: str = "6000k",
        codec: str = "libx264",
        preset: str = "veryfast",
        keyframe_interval: int = 60,
    ):
        self.rtmp_url = rtmp_url
        self.width = width
        self.height = height
        self.fps = fps
        self.bitrate = bitrate
        self.codec = codec
        self.preset = preset
        self.keyframe_interval = keyframe_interval
        self._proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found in PATH")
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.fps),
            "-i", "-",
            "-c:v", self.codec,
            "-preset", self.preset,
            "-b:v", self.bitrate,
            "-maxrate", self.bitrate,
            "-bufsize", f"{int(self.bitrate.rstrip('k')) * 2}k" if self.bitrate.endswith("k") else self.bitrate,
            "-pix_fmt", "yuv420p",
            "-g", str(self.keyframe_interval),
            "-f", "flv",
            self.rtmp_url,
        ]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        log.info("Streaming to %s", self.rtmp_url)

    def write(self, frame_bgr) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("Streamer not started")
        self._proc.stdin.write(frame_bgr.tobytes())

    def stop(self) -> None:
        if self._proc:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
