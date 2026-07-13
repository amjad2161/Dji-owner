"""
SkyCore Panorama Mission (Legal)
360° panorama + vertical pano generator
"""

import pandas as pd
import numpy as np

def generate_panorama(poi: tuple, radius_m: float = 5, shots: int = 12, altitude: float = 30):
    """Generate 360° panorama waypoints"""
    rows = []
    lat, lon = poi
    for i in range(shots):
        angle = 360 * i / shots
        lat_off = (radius_m / 111320) * np.cos(np.radians(angle))
        lon_off = (radius_m / (111320 * np.cos(np.radians(lat)))) * np.sin(np.radians(angle))
        rows.append({
            "latitude": round(lat + lat_off, 6),
            "longitude": round(lon + lon_off, 6),
            "altitude(m)": altitude,
            "heading(deg)": angle,
            "action": "photo"
        })
    return pd.DataFrame(rows)
