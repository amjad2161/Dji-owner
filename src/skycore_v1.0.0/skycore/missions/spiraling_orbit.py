"""
SkyCore Spiraling Orbit (Legal)
Ascending/descending spiral for cinematic shots
"""

import pandas as pd
import numpy as np

def generate_spiraling_orbit(poi: tuple, start_radius: float = 20, end_radius: float = 60, 
                             start_alt: float = 20, end_alt: float = 60, turns: int = 3):
    rows = []
    lat, lon = poi
    for t in range(turns * 12):
        progress = t / (turns * 12)
        radius = start_radius + (end_radius - start_radius) * progress
        alt = start_alt + (end_alt - start_alt) * progress
        angle = 360 * t / 12
        lat_off = (radius / 111320) * np.cos(np.radians(angle))
        lon_off = (radius / (111320 * np.cos(np.radians(lat)))) * np.sin(np.radians(angle))
        rows.append({
            "latitude": round(lat + lat_off, 6),
            "longitude": round(lon + lon_off, 6),
            "altitude(m)": round(alt, 1),
            "heading(deg)": angle,
            "action": "photo"
        })
    return pd.DataFrame(rows)
