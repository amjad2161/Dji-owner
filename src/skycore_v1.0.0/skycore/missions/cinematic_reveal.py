"""
SkyCore Cinematic Reveal Mission (Legal)
Dramatic pull-back + orbit combo
"""

import pandas as pd
import numpy as np

def generate_cinematic_reveal(poi: tuple, start_dist: float = 10, end_dist: float = 80, 
                              start_alt: float = 15, end_alt: float = 45):
    rows = []
    lat, lon = poi
    for i in range(20):
        progress = i / 19
        dist = start_dist + (end_dist - start_dist) * progress
        alt = start_alt + (end_alt - start_alt) * progress
        angle = 180 * progress  # slow reveal turn
        lat_off = (dist / 111320) * np.cos(np.radians(angle))
        lon_off = (dist / (111320 * np.cos(np.radians(lat)))) * np.sin(np.radians(angle))
        rows.append({
            "latitude": round(lat + lat_off, 6),
            "longitude": round(lon + lon_off, 6),
            "altitude(m)": round(alt, 1),
            "heading(deg)": angle,
            "action": "video_start" if i == 0 else "photo"
        })
    return pd.DataFrame(rows)
