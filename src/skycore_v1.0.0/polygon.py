"""Polygon-based geofence (in addition to circular radius from GeofenceConfig).

Loads polygon boundaries from KML or GeoJSON and enforces that flight stays
inside (or, if inverted, outside) the polygon. Uses `shapely` for geometry.
"""
from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from skycore.core.types import GeoPoint

log = logging.getLogger(__name__)


@dataclass
class PolygonGeofence:
    """A geofence defined by a polygon in lat/lon space."""

    points: list[tuple[float, float]] = field(default_factory=list)  # (lat, lon)
    name: str = "geofence"
    inverted: bool = False  # True → drone must stay OUTSIDE the polygon

    def contains(self, point: GeoPoint) -> bool:
        try:
            from shapely.geometry import Point, Polygon
        except ImportError as e:
            raise ImportError("shapely is required. pip install shapely") from e
        p = Point(point.lat, point.lon)
        poly = Polygon(self.points)
        inside = poly.contains(p)
        return (not inside) if self.inverted else inside

    def is_violation(self, point: GeoPoint) -> bool:
        return not self.contains(point)


def load_kml(path: Path | str) -> PolygonGeofence:
    """Load the first <Polygon> from a KML file."""
    p = Path(path)
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    root = ET.parse(p).getroot()
    coords_elem = root.find(".//kml:Polygon//kml:coordinates", ns)
    if coords_elem is None or not coords_elem.text:
        raise ValueError("No <Polygon><coordinates> in KML")
    pts = []
    for token in coords_elem.text.strip().split():
        parts = token.split(",")
        lon, lat = float(parts[0]), float(parts[1])
        pts.append((lat, lon))
    return PolygonGeofence(points=pts, name=p.stem)


def load_geojson(path: Path | str) -> PolygonGeofence:
    """Load the first Polygon feature from a GeoJSON file."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    feats = data.get("features") if data.get("type") == "FeatureCollection" else [data]
    for feat in feats:
        geom = feat.get("geometry", feat) if isinstance(feat, dict) else None
        if not geom:
            continue
        if geom.get("type") == "Polygon":
            ring = geom["coordinates"][0]
            pts = [(c[1], c[0]) for c in ring]
            return PolygonGeofence(points=pts, name=p.stem)
    raise ValueError("No Polygon feature in GeoJSON")
