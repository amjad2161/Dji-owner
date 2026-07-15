"""Panorama stitching.

Wraps OpenCV's `Stitcher` to stitch multi-image panoramas. Works on the
output of `panorama_mission` from `skycore.templates`.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)


def stitch_panorama(
    images: Iterable[Path | str],
    output_path: Path | str,
    mode: str = "panorama",
    crop: bool = True,
) -> None:
    """Stitch a series of overlapping images into a panorama.

    mode: "panorama" (cylindrical) or "scans" (planar - good for nadir mapping).
    """
    try:
        import cv2
    except ImportError as e:
        raise ImportError("opencv-python is required. pip install opencv-python") from e

    paths = [Path(p) for p in images]
    if len(paths) < 2:
        raise ValueError("need >= 2 images for a panorama")
    bgr = [cv2.imread(str(p)) for p in paths]
    if any(img is None for img in bgr):
        bad = [p for p, im in zip(paths, bgr) if im is None]
        raise FileNotFoundError(f"could not read: {bad}")

    flag = cv2.Stitcher_PANORAMA if mode == "panorama" else cv2.Stitcher_SCANS
    stitcher = cv2.Stitcher.create(flag)
    status, pano = stitcher.stitch(bgr)
    if status != cv2.Stitcher_OK:
        codes = {1: "NEED_MORE_IMGS", 2: "HOMOGRAPHY_EST_FAIL", 3: "CAMERA_PARAMS_ADJUST_FAIL"}
        raise RuntimeError(f"stitching failed: {codes.get(status, status)}")

    if crop:
        # Trim black borders around the warped result
        gray = cv2.cvtColor(pano, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)
        coords = cv2.findNonZero(mask)
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            pano = pano[y:y + h, x:x + w]

    cv2.imwrite(str(output_path), pano)
    log.info("Panorama stitched %d images → %s", len(paths), output_path)
