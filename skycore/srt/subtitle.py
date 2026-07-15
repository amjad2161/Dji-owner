"""Generate SRT subtitle file with live telemetry overlay.

DJI's video files often ship with a sidecar `.SRT` containing flight
telemetry. This module recreates that pattern from any telemetry stream
so you can burn an overlay into edited footage with HUD info.

The SRT format is a simple text format every video player and editor
understands. Subtitle entries are time-stamped and contain plain text or
basic styling.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Iterable, Optional

log = logging.getLogger(__name__)


def format_srt_overlay(sample: dict) -> str:
    """Format a single telemetry sample into a multi-line SRT block body.

    Compatible with the structure DJI Pilot 2 / DJI Fly write into their
    bundled SRT sidecars: GPS, altitude, speed, ISO, EV, S/Sh.
    """
    pos = sample.get("position", {})
    batt = sample.get("battery", {}) or {}
    gps = sample.get("gps", {}) or {}
    lines = [
        f"GPS ({pos.get('lat', 0):.6f}, {pos.get('lon', 0):.6f})",
        f"Alt {pos.get('alt', 0):.1f} m  Mode {sample.get('mode', '')}",
        f"Yaw {sample.get('yaw', 0):.0f}°  Pitch {sample.get('pitch', 0):.0f}°",
        f"Battery {batt.get('percent', 0):.0f}%  {batt.get('voltage', 0):.2f} V  GPS {gps.get('satellites', 0)} sats",
    ]
    return "\n".join(lines)


def _format_time(td: timedelta) -> str:
    total_ms = int(td.total_seconds() * 1000)
    h = total_ms // 3_600_000
    m = (total_ms % 3_600_000) // 60_000
    s = (total_ms % 60_000) // 1000
    ms = total_ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt_from_telemetry(
    samples: Iterable[dict],
    output_path: Path | str,
    start_offset_s: float = 0.0,
    sample_duration_s: float = 0.5,
    max_entries: Optional[int] = None,
) -> int:
    """Build an SRT from telemetry samples.

    Each sample becomes one subtitle visible for `sample_duration_s`. The
    first subtitle starts at `start_offset_s` (use this to offset against a
    video that started recording before telemetry).
    Returns the number of entries written.
    """
    p = Path(output_path)
    rows = list(samples)
    if max_entries is not None:
        rows = rows[:max_entries]
    if not rows:
        p.write_text("", encoding="utf-8")
        return 0

    lines = []
    cur = timedelta(seconds=start_offset_s)
    dur = timedelta(seconds=sample_duration_s)
    for i, sample in enumerate(rows, start=1):
        body = format_srt_overlay(sample)
        lines.append(str(i))
        lines.append(f"{_format_time(cur)} --> {_format_time(cur + dur)}")
        lines.append(body)
        lines.append("")
        cur += dur
    p.write_text("\n".join(lines), encoding="utf-8")
    return len(rows)
