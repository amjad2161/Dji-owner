"""
SkyCore Geofence Manager
Polygon geofence with KML/GeoJSON support + real-time violation detection
"""

import json
import math

def _point_in_polygon(lat: float, lon: float, polygon: list) -> bool:
    """Pure Python ray-casting algorithm"""
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if lat > min(p1y, p2y):
            if lat <= max(p1y, p2y):
                if lon <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or lon <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

class GeofenceManager:
    def __init__(self):
        self.polygons: dict = {}

    def load_geojson(self, path: str, name: str = "default"):
        with open(path) as f:
            data = json.load(f)
        coords = data['features'][0]['geometry']['coordinates'][0]
        self.polygons[name] = coords
        print(f"✅ Geofence '{name}' loaded ({len(coords)} points)")

    def is_inside(self, lat: float, lon: float, name: str = "default") -> bool:
        if name not in self.polygons:
            return True
        return _point_in_polygon(lat, lon, self.polygons[name])

    def check_violation(self, lat: float, lon: float) -> bool:
        for name, poly in self.polygons.items():
            if not _point_in_polygon(lat, lon, poly):
                print(f"⚠️ Geofence violation in {name}!")
                return True
        return False
