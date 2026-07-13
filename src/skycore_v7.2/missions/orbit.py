"""
SkyCore Orbit Mission Generator
Legal waypoint orbit around POI for DJI / Litchi export.
"""

import pandas as pd
import numpy as np
from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class GeoPoint:
    lat: float
    lon: float
    alt: float = 30.0

def generate_orbit_mission(
    poi: GeoPoint,
    radius_m: float = 60.0,
    altitude_m: float = 40.0,
    waypoints: int = 12,
    speed_mps: float = 4.0,
    gimbal_pitch: float = -30.0
) -> pd.DataFrame:
    """
    Generate Litchi-compatible CSV for circular orbit mission.
    """
    columns = [
        'latitude', 'longitude', 'altitude(m)', 'heading(deg)', 'curvesize(m)',
        'rotationdir', 'gimbalmode', 'gimbalpitchangle',
        'actiontype1', 'actionparam1', 'actiontype2', 'actionparam2',
        'altitudemode', 'speed(m/s)', 'poi_latitude', 'poi_longitude', 'poi_altitude(m)'
    ]
    
    rows = []
    for i in range(waypoints):
        angle = 2 * np.pi * i / waypoints
        lat = poi.lat + (radius_m / 111320) * np.cos(angle)  # approx degrees
        lon = poi.lon + (radius_m / (111320 * np.cos(np.radians(poi.lat)))) * np.sin(angle)
        
        row = {
            'latitude': round(lat, 6),
            'longitude': round(lon, 6),
            'altitude(m)': altitude_m,
            'heading(deg)': round(np.degrees(angle), 1),
            'curvesize(m)': 15,
            'rotationdir': 0,
            'gimbalmode': 2,
            'gimbalpitchangle': gimbal_pitch,
            'actiontype1': -1,
            'actionparam1': 0,
            # ... fill all action columns as -1,0
            'altitudemode': 0,
            'speed(m/s)': speed_mps,
            'poi_latitude': poi.lat,
            'poi_longitude': poi.lon,
            'poi_altitude(m)': poi.alt
        }
        # Add all action columns
        for j in range(1, 16):
            row[f'actiontype{j}'] = -1
            row[f'actionparam{j}'] = 0
        rows.append(row)
    
    df = pd.DataFrame(rows)
    # Add header row if needed, but Litchi uses first data row
    return df

if __name__ == "__main__":
    poi = GeoPoint(37.7749, -122.4194)
    df = generate_orbit_mission(poi, radius_m=60, altitude_m=40, waypoints=12)
    df.to_csv('/home/workdir/artifacts/skycore/presets/orbit_demo.csv', index=False)
    print("Orbit mission CSV generated!")
