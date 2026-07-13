"""HDR merge for bracketed exposures.

DJI's AEB (Auto Exposure Bracketing) shoots 3, 5, or 7 photos at different
exposures. Merge them into a single HDR via OpenCV's MergeMertens or Debevec.

Mertens (default) is robust and tonemap-free — the output is already in
LDR. Use Debevec when you want full HDR float for advanced tonemapping.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)


def merge_hdr(
    images: Iterable[Path | str],
    output_path: Path | str,
    method: str = "mertens",
    tonemap_gamma: float = 1.4,
) -> None:
    """Merge a bracketed set into a single HDR-tonemapped image.

    method:
        "mertens"  — fast, stable; LDR output; recommended default
        "debevec"  — true HDR → Drago tonemap; better dynamic range
    """
    try:
        import cv2
        import numpy as np
    except ImportError as e:
        raise ImportError("opencv-python is required. pip install opencv-python") from e

    paths = [Path(p) for p in images]
    if len(paths) < 2:
        raise ValueError("need >= 2 bracketed images")
    bgr = [cv2.imread(str(p)) for p in paths]
    if any(img is None for img in bgr):
        bad = [p for p, im in zip(paths, bgr) if im is None]
        raise FileNotFoundError(f"could not read: {bad}")

    if method == "mertens":
        merger = cv2.createMergeMertens()
        fused = merger.process(bgr)
        result = (np.clip(fused * 255, 0, 255)).astype(np.uint8)
    elif method == "debevec":
        # Without per-image EXIF exposure data, assume an evenly-spaced bracket
        n = len(bgr)
        exposures = np.array([2.0 ** (i - (n - 1) / 2) for i in range(n)], dtype=np.float32)
        merger = cv2.createMergeDebevec()
        hdr = merger.process(bgr, times=exposures.copy())
        tonemap = cv2.createTonemapDrago(gamma=tonemap_gamma)
        ldr = tonemap.process(hdr)
        result = (np.clip(ldr * 255, 0, 255)).astype(np.uint8)
    else:
        raise ValueError(f"unknown method: {method}")

    cv2.imwrite(str(output_path), result)
    log.info("HDR merged %d images → %s", len(paths), output_path)
