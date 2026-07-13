"""
SkyCore Analytics - Flight Log Analyzer
Parses DJI / Litchi / SkyCore CSV logs into FlightSummary
"""

import pandas as pd
from dataclasses import dataclass
from typing import Dict

@dataclass
class FlightSummary:
    duration_min: float
    max_altitude: float
    avg_speed: float
    distance_km: float
    battery_used: float
    issues: list

class FlightLogAnalyzer:
    def analyze(self, csv_path: str) -> FlightSummary:
        df = pd.read_csv(csv_path)
        
        # Basic calculations (assumes standard columns)
        duration = len(df) * 0.5 / 60  # assume 2Hz
        max_alt = df['altitude(m)'].max() if 'altitude(m)' in df.columns else 0
        avg_speed = df['speed(m/s)'].mean() if 'speed(m/s)' in df.columns else 0
        distance = (df['latitude'].diff()**2 + df['longitude'].diff()**2).sum()**0.5 * 111.32
        
        issues = []
        if max_alt > 120:
            issues.append("Exceeded 120m altitude limit")
        if avg_speed > 15:
            issues.append("High speed detected")
            
        return FlightSummary(
            duration_min=round(duration, 1),
            max_altitude=round(max_alt, 1),
            avg_speed=round(avg_speed, 1),
            distance_km=round(distance, 2),
            battery_used=15.0,  # placeholder
            issues=issues
        )

if __name__ == "__main__":
    analyzer = FlightLogAnalyzer()
    summary = analyzer.analyze("presets/orbit-template.csv")
    print(summary)
