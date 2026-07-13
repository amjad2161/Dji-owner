"""
SkyCore Building Inspection Mission (Legal)
Spiraling orbit + facade + vertical pano combo
"""

import pandas as pd
from missions.orbit import generate_orbit_mission
from missions.facade import generate_facade

def generate_building_inspection(poi: tuple, radius: float = 25, height: float = 50):
    orbit = generate_orbit_mission(poi, radius_m=radius, altitude_m=height, waypoints=8)
    facade = generate_facade(poi, height_m=height, passes=2)
    return pd.concat([orbit, facade], ignore_index=True)
