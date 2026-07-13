"""
SkyCore SAR - Search & Rescue Patterns
Coast Guard / Civil Defense compatible mission generators
"""

import pandas as pd
import numpy as np
from typing import List

def generate_expanding_square(center: tuple, spacing_m: float = 20.0, legs: int = 6) -> pd.DataFrame:
    """Expanding Square search pattern (standard SAR)"""
    rows = []
    lat, lon = center
    direction = 0
    leg_length = spacing_m
    
    for leg in range(legs):
        for _ in range(2):  # two legs per expansion
            for i in range(int(leg_length / 5)):
                lat += (5 / 111320) * np.cos(np.radians(direction))
                lon += (5 / (111320 * np.cos(np.radians(lat)))) * np.sin(np.radians(direction))
                rows.append({
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "altitude(m)": 40,
                    "action": "search",
                    "pattern": "expanding_square"
                })
            direction = (direction + 90) % 360
        leg_length += spacing_m * 1.5
    
    return pd.DataFrame(rows)

def generate_creeping_line(start: tuple, end: tuple, width_m: float = 100.0, spacing: float = 15.0):
    """Creeping Line search pattern"""
    # Implementation simplified for demo
    print(f"🛟 Generating Creeping Line from {start} to {end}, width {width_m}m")
    return pd.DataFrame([{"pattern": "creeping_line", "start": start, "end": end}])
