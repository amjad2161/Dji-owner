"""Flight sidecar manifest.

A single JSON file that bundles every artifact for a flight: video paths,
photo paths, telemetry summary, weather snapshot, mission plan, and
operator metadata. Drop next to the footage in your archive folder.

The schema is intentionally flat and self-describing so you can generate
reports or re-import flights without parsing five different formats.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class ManifestSection:
    """A named section of the manifest."""

    label: str
    data: dict = field(default_factory=dict)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(
    flight_id: Optional[int] = None,
    drone_name: str = "",
    drone_model: str = "",
    operator: str = "",
    started_at: Optional[datetime] = None,
    ended_at: Optional[datetime] = None,
    home: Optional[dict] = None,
    videos: Optional[list[Path | str]] = None,
    photos: Optional[list[Path | str]] = None,
    telemetry_summary: Optional[dict] = None,
    weather: Optional[dict] = None,
    mission: Optional[dict] = None,
    notes: str = "",
    extra: Optional[dict] = None,
    hash_files: bool = False,
) -> dict:
    """Build a structured manifest dictionary."""
    def file_entry(p: Path | str) -> dict:
        path = Path(p)
        e = {
            "path": str(path),
            "name": path.name,
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "exists": path.exists(),
        }
        if hash_files and path.exists():
            try:
                e["sha256"] = _sha256(path)
            except Exception as ex:
                e["sha256_error"] = str(ex)
        return e

    return {
        "schema": "skycore-flight-manifest/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "flight_id": flight_id,
        "drone": {"name": drone_name, "model": drone_model},
        "operator": operator,
        "timing": {
            "started_at": started_at.isoformat() if started_at else None,
            "ended_at": ended_at.isoformat() if ended_at else None,
        },
        "home": home,
        "artifacts": {
            "videos": [file_entry(v) for v in (videos or [])],
            "photos": [file_entry(p) for p in (photos or [])],
        },
        "telemetry": telemetry_summary or {},
        "weather": weather or {},
        "mission": mission or {},
        "notes": notes,
        "extra": extra or {},
    }


def write_manifest(path: Path | str, manifest: dict, indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=indent, default=str), encoding="utf-8")
    log.info("Wrote manifest %s", p)
