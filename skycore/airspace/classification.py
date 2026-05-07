"""Airspace classification using OpenAIP GeoJSON exports.

OpenAIP (https://www.openaip.net) publishes free airspace data as GeoJSON.
Download the file for your country, point this module at it, and query
airspace at any (lat, lon) before flight.

Classes follow ICAO conventions:
  A, B, C, D, E, F, G  (controlled → uncontrolled)
  CTR  control zone
  TMA  terminal control area
  R    restricted
  D    danger
  P    prohibited
  W    warning
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from skycore.core.types import GeoPoint

log = logging.getLogger(__name__)


class AirspaceClass(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    CTR = "CTR"
    TMA = "TMA"
    RESTRICTED = "R"
    DANGER = "D-AREA"
    PROHIBITED = "P"
    WARNING = "W"
    UNKNOWN = "?"


@dataclass
class AirspaceFeature:
    name: str
    cls: AirspaceClass
    floor_m_amsl: float = 0.0
    ceiling_m_amsl: float = 99999.0
    polygon: list[tuple[float, float]] = field(default_factory=list)  # (lat, lon)
    raw: Optional[dict] = None

    def is_critical(self) -> bool:
        return self.cls in {
            AirspaceClass.PROHIBITED,
            AirspaceClass.RESTRICTED,
            AirspaceClass.DANGER,
            AirspaceClass.CTR,
        }


class AirspaceDatabase:
    """In-memory database of airspace features. Backed by polygon checks."""

    def __init__(self, features: Optional[list[AirspaceFeature]] = None):
        self.features: list[AirspaceFeature] = features or []

    def add(self, feature: AirspaceFeature) -> None:
        self.features.append(feature)

    def query(self, point: GeoPoint) -> list[AirspaceFeature]:
        """Return all airspace features intersecting the given point."""
        try:
            from shapely.geometry import Point, Polygon
        except ImportError as e:
            raise ImportError("shapely is required. pip install shapely") from e
        p = Point(point.lat, point.lon)
        out = []
        for f in self.features:
            if not f.polygon:
                continue
            if not (f.floor_m_amsl <= point.alt <= f.ceiling_m_amsl):
                continue
            if Polygon(f.polygon).contains(p):
                out.append(f)
        return out

    def is_critical_at(self, point: GeoPoint) -> tuple[bool, list[AirspaceFeature]]:
        """True if the point intersects a critical airspace."""
        hits = self.query(point)
        critical = [h for h in hits if h.is_critical()]
        return bool(critical), critical


def load_openaip_geojson(path: Path | str) -> AirspaceDatabase:
    """Load an OpenAIP GeoJSON country export.

    OpenAIP wraps each airspace as a Feature with properties incl.
    `icaoClass`, `type`, `name`, `lowerLimit`, `upperLimit`.
    """
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    features = data.get("features", [])
    db = AirspaceDatabase()
    for feat in features:
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry", {}) or {}
        if geom.get("type") != "Polygon":
            continue
        ring = geom["coordinates"][0]
        polygon = [(c[1], c[0]) for c in ring]
        cls_raw = (props.get("icaoClass") or props.get("type") or "").upper()
        try:
            cls = AirspaceClass(cls_raw)
        except ValueError:
            if "PROHIBIT" in cls_raw:
                cls = AirspaceClass.PROHIBITED
            elif "RESTRICT" in cls_raw:
                cls = AirspaceClass.RESTRICTED
            elif "DANGER" in cls_raw:
                cls = AirspaceClass.DANGER
            elif "CTR" in cls_raw:
                cls = AirspaceClass.CTR
            elif "TMA" in cls_raw:
                cls = AirspaceClass.TMA
            else:
                cls = AirspaceClass.UNKNOWN
        db.add(
            AirspaceFeature(
                name=props.get("name", "unnamed"),
                cls=cls,
                floor_m_amsl=float(props.get("lowerLimit", {}).get("value", 0) or 0),
                ceiling_m_amsl=float(props.get("upperLimit", {}).get("value", 99999) or 99999),
                polygon=polygon,
                raw=props,
            )
        )
    log.info("Loaded %d airspace features from %s", len(db.features), p)
    return db
