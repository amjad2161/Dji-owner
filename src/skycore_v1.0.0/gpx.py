"""GPX export for recorded tracks.

GPX opens in Strava, Garmin Connect, GPSBabel, and most fitness / mapping tools.
"""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


def telemetry_to_gpx(
    samples: Iterable[dict],
    output_path: Path | str,
    name: str = "flight",
    creator: str = "SkyCore",
) -> None:
    """Recorded flight track as a GPX file.

    Each sample requires lat, lon, optionally alt and ts (ISO timestamp).
    """
    p = Path(output_path)
    pts = []
    for s in samples:
        ts = s.get("ts") or s.get("timestamp") or ""
        ele = s.get("alt", 0)
        elem = (
            f'      <trkpt lat="{s["lat"]:.7f}" lon="{s["lon"]:.7f}">'
            f"<ele>{ele}</ele>"
            f"<time>{html.escape(str(ts))}</time>"
            f"</trkpt>"
        )
        pts.append(elem)
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="{html.escape(creator)}" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>{html.escape(name)}</name>
    <trkseg>
{chr(10).join(pts)}
    </trkseg>
  </trk>
</gpx>
"""
    p.write_text(body, encoding="utf-8")
