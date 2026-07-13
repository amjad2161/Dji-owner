"""
SkyCore Log Replay
Replay recorded flights on simulator for analysis
"""

import pandas as pd
import asyncio
from core.drone import SimulatorDrone

async def replay_flight(csv_path: str, speed_factor: float = 1.0):
    df = pd.read_csv(csv_path)
    drone = SimulatorDrone()
    await drone.connect()
    
    print(f"▶️ Replaying {len(df)} waypoints...")
    for _, row in df.iterrows():
        await drone.goto(row['latitude'], row['longitude'], row['altitude(m)'])
        await asyncio.sleep(0.5 / speed_factor)
    
    print("✅ Replay complete")
