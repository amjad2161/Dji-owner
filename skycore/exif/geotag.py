"""EXIF geotagging for drone photos.

DJI drones already write GPS EXIF on Mavic 2 / 3 / Air / Mini cameras.
This module is for cases where:
  - Photos came from a payload camera without GPS
  - Photos lost EXIF in editing
  - You want to backfill geotags from a recorded telemetry log

Uses `piexif` (small, no compiled extensions).
"""
from __future__ import annotations

import bisect
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def _to_dms_rational(deg: float) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """Decimal degrees → EXIF DMS-rational format."""
    deg = abs(deg)
    d = int(deg)
    m_full = (deg - d) * 60
    m = int(m_full)
    s = round((m_full - m) * 60 * 100)  # 0.01 sec resolution
    return ((d, 1), (m, 1), (s, 100))


def geotag_photo(
    image_path: Path | str,
    lat: float,
    lon: float,
    altitude_m: float,
    timestamp: Optional[datetime] = None,
) -> None:
    """Write GPS tags into the EXIF of a single image (in-place)."""
    try:
        import piexif
    except ImportError as e:
        raise ImportError("piexif is required. pip install piexif") from e

    p = Path(image_path)
    try:
        ed = piexif.load(str(p))
    except Exception:
        ed = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    gps = {
        piexif.GPSIFD.GPSLatitudeRef: "N" if lat >= 0 else "S",
        piexif.GPSIFD.GPSLatitude: _to_dms_rational(lat),
        piexif.GPSIFD.GPSLongitudeRef: "E" if lon >= 0 else "W",
        piexif.GPSIFD.GPSLongitude: _to_dms_rational(lon),
        piexif.GPSIFD.GPSAltitudeRef: 0 if altitude_m >= 0 else 1,
        piexif.GPSIFD.GPSAltitude: (int(round(abs(altitude_m) * 100)), 100),
    }
    if timestamp:
        gps[piexif.GPSIFD.GPSDateStamp] = timestamp.strftime("%Y:%m:%d")
        gps[piexif.GPSIFD.GPSTimeStamp] = (
            (timestamp.hour, 1),
            (timestamp.minute, 1),
            (int(timestamp.second), 1),
        )
    ed["GPS"] = gps
    piexif.insert(piexif.dump(ed), str(p))


def geotag_directory_from_telemetry(
    images_dir: Path | str,
    telemetry: list[dict],
    glob_pattern: str = "*.jpg",
) -> int:
    """Geotag every image in a directory using nearest-time telemetry.

    `telemetry` is a list of dicts with keys: ts (ISO string), lat, lon, alt.
    Returns count of images tagged.
    """
    if not telemetry:
        return 0
    sorted_tm = sorted(telemetry, key=lambda x: x.get("ts", ""))
    timestamps = [datetime.fromisoformat(t["ts"]) for t in sorted_tm]
    timestamps_ts = [t.timestamp() for t in timestamps]

    d = Path(images_dir)
    count = 0
    for img in sorted(d.glob(glob_pattern)):
        try:
            mtime = datetime.fromtimestamp(img.stat().st_mtime)
        except Exception:
            continue
        idx = bisect.bisect_left(timestamps_ts, mtime.timestamp())
        if idx >= len(sorted_tm):
            idx = len(sorted_tm) - 1
        elif idx > 0:
            # pick the closer of idx and idx-1
            if abs(timestamps_ts[idx] - mtime.timestamp()) > abs(timestamps_ts[idx - 1] - mtime.timestamp()):
                idx -= 1
        t = sorted_tm[idx]
        try:
            geotag_photo(img, t["lat"], t["lon"], t.get("alt", 0), timestamps[idx])
            count += 1
        except Exception as e:
            log.warning("Failed to tag %s: %s", img, e)
    return count
