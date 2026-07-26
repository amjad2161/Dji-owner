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
from urllib.parse import urlparse

log = logging.getLogger(__name__)

# Only live-stream ingest schemes — blocks file://, http(s)://, concat and other
# local-file / SSRF vectors from reaching ffmpeg -i.
_ALLOWED_INPUT_SCHEMES = ("rtmp", "rtmps", "rtsp", "rtsps", "srt", "udp", "rtp")


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
        scheme = urlparse(self.input_url).scheme.lower()
        if scheme not in _ALLOWED_INPUT_SCHEMES:
            raise ValueError(
                f"input_url scheme '{scheme}' is not permitted; allowed: {_ALLOWED_INPUT_SCHEMES}"
            )
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
        # capture ffmpeg stderr to a log so failures are diagnosable (was DEVNULL)
        self._log_fh = open(self.output_dir / "ffmpeg.log", "wb")
        self._proc = subprocess.Popen(cmd, stderr=self._log_fh)

    def stop(self) -> None:
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        fh = getattr(self, "_log_fh", None)
        if fh:
            fh.close()
            self._log_fh = None
            self._proc = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None
