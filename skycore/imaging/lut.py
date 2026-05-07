"""Apply 3D LUT (.cube) to images.

Accepts standard 3D LUT files (Resolve / DJI / Filmmaker presets export
to .cube). Useful for batch color-grading drone JPEG / PNG output.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def _parse_cube_lut(path: Path) -> tuple[int, list[tuple[float, float, float]]]:
    """Parse a .cube 3D LUT into (size, ordered list of (r,g,b) entries)."""
    size = 0
    entries: list[tuple[float, float, float]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.upper().startswith("LUT_3D_SIZE"):
                size = int(line.split()[1])
                continue
            if line.upper().startswith(("TITLE", "DOMAIN_MIN", "DOMAIN_MAX", "LUT_1D_SIZE", "LUT_2D_SIZE")):
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    entries.append((float(parts[0]), float(parts[1]), float(parts[2])))
                except ValueError:
                    continue
    if size == 0 or len(entries) != size ** 3:
        raise ValueError(f"Invalid .cube LUT: size={size}, entries={len(entries)}")
    return size, entries


def apply_cube_lut(image_path: Path | str, lut_path: Path | str, output_path: Path | str) -> None:
    """Apply a .cube 3D LUT to an image."""
    try:
        import cv2
        import numpy as np
    except ImportError as e:
        raise ImportError("opencv-python is required. pip install opencv-python") from e

    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(image_path)

    size, entries = _parse_cube_lut(Path(lut_path))
    lut3d = np.array(entries, dtype=np.float32).reshape((size, size, size, 3))

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    idx = (rgb * (size - 1)).astype(np.int32)
    idx = np.clip(idx, 0, size - 1)
    out = lut3d[idx[..., 0], idx[..., 1], idx[..., 2]]
    out = np.clip(out * 255, 0, 255).astype(np.uint8)
    out_bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(output_path), out_bgr)
    log.info("Applied LUT %s to %s → %s", Path(lut_path).name, Path(image_path).name, output_path)
