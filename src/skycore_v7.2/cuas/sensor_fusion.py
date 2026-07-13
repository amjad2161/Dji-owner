"""
SkyCore Multi-Sensor Fusion for Counter-UAS
Combines ADS-B, RF, Vision, Audio for robust detection
"""

from typing import List, Dict
from dataclasses import dataclass

@dataclass
class FusedDetection:
    position: tuple
    altitude: float
    velocity: tuple
    confidence: float
    sensors: List[str]  # Which sensors detected it
    classification: str

class SensorFusion:
    def fuse(self, detections: List[Dict]) -> List[FusedDetection]:
        """Fuse data from multiple sensors"""
        fused = []
        for det in detections:
            sensors = []
            conf = 0.5
            
            if det.get('adsb'):
                sensors.append('ADS-B')
                conf += 0.3
            if det.get('rf'):
                sensors.append('RF')
                conf += 0.25
            if det.get('vision'):
                sensors.append('Vision')
                conf += 0.2
            if det.get('audio'):
                sensors.append('Audio')
                conf += 0.15
            
            fused.append(FusedDetection(
                position=det.get('position', (0,0)),
                altitude=det.get('altitude', 0),
                velocity=det.get('velocity', (0,0,0)),
                confidence=min(0.99, conf),
                sensors=sensors,
                classification=det.get('classification', 'Unknown')
            ))
        return fused
