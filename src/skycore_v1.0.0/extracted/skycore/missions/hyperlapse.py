"""
SkyCore Hyperlapse Mission (Legal)
Time-lapse orbit / reveal generator
"""

import pandas as pd
import numpy as np

def generate_hyperlapse(poi: tuple, radius_m: float = 30, duration_sec: int = 30, altitude: float = 40):
    """Generate hyperlapse orbit"""
    shots = duration_sec // 2
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
            "action": "photo_interval"
        })
    return pd.DataFrame(rows)
