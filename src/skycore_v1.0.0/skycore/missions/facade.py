"""
SkyCore Facade Scan Mission (Legal)
Vertical building inspection pattern
"""

import pandas as pd
import numpy as np

def generate_facade(base: tuple, height_m: float = 40, passes: int = 4, spacing_m: float = 8):
    """Generate facade scanning pattern"""
    rows = []
    lat, lon = base
    for p in range(passes):
        for h in range(0, int(height_m), 5):
            rows.append({
                "latitude": round(lat + (p * spacing_m / 111320), 6),
                "longitude": round(lon, 6),
                "altitude(m)": h,
                "action": "photo"
            })
    return pd.DataFrame(rows)
