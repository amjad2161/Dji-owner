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


# Best-effort OpenAIP numeric type-code -> class (the name-substring fallback in
# _classify_airspace covers any codes not listed here, so a critical zone is not missed).
_OPENAIP_TYPE_CODES = {
    1: AirspaceClass.RESTRICTED,
    2: AirspaceClass.DANGER,
    3: AirspaceClass.PROHIBITED,
    4: AirspaceClass.CTR,
    7: AirspaceClass.TMA,
}
_CRITICAL = {AirspaceClass.PROHIBITED, AirspaceClass.RESTRICTED, AirspaceClass.DANGER, AirspaceClass.CTR}


def _classify_airspace(props: dict) -> AirspaceClass:
    """Classify from any available signal — numeric OpenAIP code, string type/icaoClass,
    or a keyword in the name. Prefer a CRITICAL result so a prohibited/restricted/danger/
    CTR zone is never silently downgraded (OpenAIP GeoJSON often uses numeric codes)."""
    candidates: list[AirspaceClass] = []
    for key in ("type", "icaoClass"):
        v = props.get(key)
        if isinstance(v, (int, float)) or (isinstance(v, str) and str(v).strip().lstrip("-").isdigit()):
            mapped = _OPENAIP_TYPE_CODES.get(int(v))
            if mapped:
                candidates.append(mapped)
    text = " ".join(str(props.get(k, "")) for k in ("type", "icaoClass", "name")).upper()
    if "PROHIBIT" in text:
        candidates.append(AirspaceClass.PROHIBITED)
    if "RESTRICT" in text:
        candidates.append(AirspaceClass.RESTRICTED)
    if "DANGER" in text:
        candidates.append(AirspaceClass.DANGER)
    if "CTR" in text or "CONTROL ZONE" in text:
        candidates.append(AirspaceClass.CTR)
    if "TMA" in text:
        candidates.append(AirspaceClass.TMA)
    try:
        candidates.append(AirspaceClass(str(props.get("type") or props.get("icaoClass") or "").upper()))
    except (ValueError, TypeError):
        pass
    for c in candidates:                      # prefer any critical classification
        if c in _CRITICAL:
            return c
    return candidates[0] if candidates else AirspaceClass.UNKNOWN


def _limit_to_m_amsl(limit) -> Optional[float]:
    """Convert an OpenAIP vertical limit {value, unit, referenceDatum} to metres.
    unit: 1=ft, 6=FL(hundreds of ft), 2=m. Unknown units default to FEET (OpenAIP's
    usual unit) rather than being read as metres."""
    if not isinstance(limit, dict):
        return None
    try:
        val = float(limit.get("value"))
    except (TypeError, ValueError):
        return None
    unit = limit.get("unit")
    us = str(unit).upper()
    if unit == 6 or us in ("FL", "6"):
        return val * 100.0 * 0.3048
    if unit == 2 or us in ("M", "2", "MTR"):
        return val
    # unit 1 / "FT" / unspecified -> feet
    return val * 0.3048


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
        gtype = geom.get("type")
        if gtype == "Polygon":
            rings = [geom.get("coordinates", [[]])[0]]
        elif gtype == "MultiPolygon":                       # was silently dropped before
            rings = [poly[0] for poly in geom.get("coordinates", []) if poly]
        else:
            continue
        cls = _classify_airspace(props)
        floor = _limit_to_m_amsl(props.get("lowerLimit"))
        ceiling = _limit_to_m_amsl(props.get("upperLimit"))
        for ring in rings:
            if not ring:
                continue
            polygon = [(c[1], c[0]) for c in ring]
            db.add(
                AirspaceFeature(
                    name=props.get("name", "unnamed"),
                    cls=cls,
                    floor_m_amsl=floor if floor is not None else 0.0,
                    ceiling_m_amsl=ceiling if ceiling is not None else 99999.0,
                    polygon=polygon,
                    raw=props,
                )
            )
    log.info("Loaded %d airspace features from %s", len(db.features), p)
    return db
