"""Render a hyperlapse from a directory of photos.

Wraps ffmpeg's image-sequence encoder with sane defaults for drone
timelapse / hyperlapse output.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def render_hyperlapse(
    photos_dir: Path | str,
    output_path: Path | str,
    fps: int = 30,
    glob_pattern: str = "*.jpg",
    codec: str = "libx264",
    bitrate: str = "30M",
    resolution: Optional[str] = None,
    crop_aspect: Optional[str] = None,
    deflicker: bool = True,
    sort: bool = True,
) -> None:
    """Stitch photos into an MP4.

    photos_dir: directory containing the source frames
    output_path: e.g. "hyperlapse.mp4"
    fps: output frame rate
    deflicker: apply ffmpeg's deflicker filter to smooth exposure changes
    crop_aspect: e.g. "16:9" to centre-crop
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found in PATH")
    d = Path(photos_dir)
    if not d.exists():
        raise FileNotFoundError(d)

    photos = sorted(d.glob(glob_pattern)) if sort else list(d.glob(glob_pattern))
    if len(photos) < 2:
        raise ValueError(f"Need >= 2 photos in {d} matching {glob_pattern}")

    # Build a concat list to support arbitrary filenames
    concat = d / "_skycore_concat.txt"
    concat.write_text("\n".join(f"file '{p.resolve()}'\nduration {1/fps:.6f}" for p in photos), encoding="utf-8")
    concat.open("a", encoding="utf-8").write(f"file '{photos[-1].resolve()}'\n")

    filters = []
    if deflicker:
        filters.append("deflicker=mode=pm:size=10")
    if crop_aspect:
        try:
            num, den = (int(x) for x in crop_aspect.split(":"))
            filters.append(f"crop=w='if(gt(iw/ih,{num}/{den}),ih*{num}/{den},iw)':h='if(gt(iw/ih,{num}/{den}),ih,iw*{den}/{num})'")
        except ValueError:
            pass
    if resolution:
        filters.append(f"scale={resolution}")
    filter_chain = ",".join(filters) if filters else None

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat)]
    if filter_chain:
        cmd.extend(["-vf", filter_chain])
    cmd.extend([
        "-c:v", codec,
        "-b:v", bitrate,
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        str(output_path),
    ])
    log.info("Running ffmpeg: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, shell=False)
    finally:
        try:
            concat.unlink()
        except OSError:
            pass
