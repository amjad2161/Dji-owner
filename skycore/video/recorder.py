"""Local recorder. Pipes frames to FFmpeg via stdin to encode H.264/H.265."""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class LocalRecorder:
    def __init__(
        self,
        path: Path | str,
        width: int,
        height: int,
        fps: int = 30,
        codec: str = "libx264",
        bitrate: str = "50M",
    ):
        self.path = Path(path)
        self.width = width
        self.height = height
        self.fps = fps
        self.codec = codec
        self.bitrate = bitrate
        self._proc: Optional[subprocess.Popen] = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def start(self) -> None:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found in PATH")
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.fps),
            "-i", "-",
            "-c:v", self.codec,
            "-b:v", self.bitrate,
            "-pix_fmt", "yuv420p",
            str(self.path),
        ]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        log.info("Recording to %s", self.path)

    def write(self, frame_bgr) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise RuntimeError("Recorder not started")
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
