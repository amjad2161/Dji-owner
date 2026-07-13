"""Gyroflow CLI wrapper for batch stabilization.

Gyroflow has an excellent GUI but also a `gyroflow` CLI for headless
batch processing. We invoke it with the camera profile, smoothness
setting, and output codec.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def gyroflow_stabilize(
    input_path: Path | str,
    output_path: Path | str,
    preset: Optional[Path | str] = None,
    smoothness: float = 0.5,
    codec: str = "x264",
) -> None:
    """Run Gyroflow CLI on a single video.

    Args:
        input_path: source MP4 / MOV from the drone
        output_path: where to write the stabilized output
        preset: optional .gyroflow preset file (overrides everything)
        smoothness: 0.0–1.0
        codec: x264 / x265 / prores
    """
    if shutil.which("gyroflow") is None:
        raise RuntimeError("gyroflow CLI not found in PATH. See https://gyroflow.xyz")
    cmd = ["gyroflow", str(input_path), "-o", str(output_path)]
    if preset:
        cmd.extend(["--preset", str(preset)])
    cmd.extend(["--smoothness", str(smoothness), "--codec", codec])
    log.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, shell=False)
