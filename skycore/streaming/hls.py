"""HLS proxy: ingest RTMP/RTSP, output HLS for browser playback.

Useful when the drone (or RC) sends an RTMP stream and you want to embed
it in the SkyCore dashboard. Browsers play HLS via standard <video>
or hls.js. We wrap ffmpeg in a controlled subprocess.

Typical pipeline:
    drone → RC → OBS → RTMP → HlsProxy → ./hls/stream.m3u8 → browser
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class HlsProxy:
    input_url: str
    output_dir: Path | str
    segment_seconds: int = 2
    list_size: int = 6
    codec: str = "libx264"
    preset: str = "veryfast"
    bitrate: str = "6000k"

    def __post_init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def playlist_path(self) -> Path:
        return self.output_dir / "stream.m3u8"

    def start(self) -> None:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found in PATH")
        cmd = [
            "ffmpeg", "-y",
            "-i", self.input_url,
            "-c:v", self.codec,
            "-preset", self.preset,
            "-b:v", self.bitrate,
            "-g", str(self.segment_seconds * 30),
            "-c:a", "aac",
            "-b:a", "128k",
            "-f", "hls",
            "-hls_time", str(self.segment_seconds),
            "-hls_list_size", str(self.list_size),
            "-hls_flags", "delete_segments+independent_segments",
            "-hls_segment_filename", str(self.output_dir / "seg-%05d.ts"),
            str(self.playlist_path),
        ]
        log.info("Starting HLS proxy: %s", " ".join(cmd))
        self._proc = subprocess.Popen(cmd, stderr=subprocess.DEVNULL)

    def stop(self) -> None:
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None
