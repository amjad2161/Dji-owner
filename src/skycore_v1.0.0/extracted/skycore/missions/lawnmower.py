"""
SkyCore Lawnmower / Survey Mission (Legal)
Grid survey pattern for mapping and inspection
"""

import pandas as pd
import numpy as np

def generate_lawnmower(poi: tuple, width_m: float = 100, length_m: float = 150, 
                       spacing_m: float = 15, altitude: float = 50) -> pd.DataFrame:
    """Generate lawnmower survey pattern"""
    rows = []
    lat, lon = poi
    direction = 0
    steps = int(length_m / 5)
    
    for i in range(int(width_m / spacing_m)):
        for j in range(steps):
            lat_offset = (j * 5 / 111320) * np.cos(np.radians(direction))
            lon_offset = (j * 5 / (111320 * np.cos(np.radians(lat)))) * np.sin(np.radians(direction))
            rows.append({
                "latitude": round(lat + lat_offset, 6),
                "longitude": round(lon + lon_offset, 6),
                "altitude(m)": altitude,
                "action": "photo"
            })
        direction = (direction + 180) % 360
        lat += (spacing_m / 111320) * np.cos(np.radians(90))
    
    return pd.DataFrame(rows)
