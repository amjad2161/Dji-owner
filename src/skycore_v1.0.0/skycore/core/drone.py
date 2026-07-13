"""
SkyCore Core Drone ABC
Unified interface for all backends: Simulator, Tello, MAVLink, DJI Bridge
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Callable
import asyncio

@dataclass
class GeoPoint:
    lat: float
    lon: float
    alt: float = 30.0

@dataclass
class Telemetry:
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    heading: float = 0.0
    battery: float = 100.0
    link_quality: float = 1.0
    speed: float = 0.0

class Drone(ABC):
    """Abstract base for all drone backends"""
    
    def __init__(self, home: Optional['GeoPoint'] = None):
        self.home = home
        self._telemetry = Telemetry()
        self._connected = False
        self._event_handlers: dict = {}
    
    @abstractmethod
    async def connect(self):
        pass
    
    @abstractmethod
    async def takeoff(self):
        pass
    
    @abstractmethod
    async def land(self):
        pass
    
    @abstractmethod
    async def goto(self, lat: float, lon: float, alt: float):
        pass
    
    async def get_telemetry(self) -> Telemetry:
        return self._telemetry
    
    def on_event(self, event: str, handler: Callable):
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
    
    async def emit(self, event: str, data: dict = None):
        for handler in self._event_handlers.get(event, []):
            await handler(data or {})

# Example Simulator
class SimulatorDrone(Drone):
    async def connect(self):
        self._connected = True
        print("Simulator connected")
    
    async def takeoff(self):
        print("Simulator takeoff")
        self._telemetry.alt = 10.0
    
    async def land(self):
        print("Simulator land")
        self._telemetry.alt = 0.0
    
    async def goto(self, lat: float, lon: float, alt: float):
        print(f"Simulator goto {lat}, {lon}, {alt}")
        self._telemetry.lat = lat
        self._telemetry.lon = lon
        self._telemetry.alt = alt

    # ========== LIVE CAMERA SUPPORT ==========
    async def get_camera_frame(self) -> bytes:
        """Return a single JPEG frame from drone camera (simulated for demo)"""
        from PIL import Image, ImageDraw, ImageFont
        import io
        import time
        
        # Create a mock "live" camera frame (1280x720)
        img = Image.new('RGB', (1280, 720), color=(20, 40, 60))  # Dark blue sky-like
        draw = ImageDraw.Draw(img)
        
        # Add "live" elements
        timestamp = time.strftime("%H:%M:%S")
        draw.text((50, 50), f"LIVE DRONE CAM - {timestamp}", fill=(0, 255, 0))
        draw.text((50, 100), f"Lat: {self._telemetry.lat:.4f} Lon: {self._telemetry.lon:.4f} Alt: {self._telemetry.alt:.1f}m", fill=(255, 255, 255))
        draw.text((50, 150), "BATTERY: 87% | LINK: EXCELLENT | RECORDING: ON", fill=(0, 255, 255))
        
        # Simple moving "target" indicator (simulates tracking)
        x = int(600 + 100 * (time.time() % 5 - 2.5))
        draw.ellipse([x-30, 300, x+30, 360], outline=(255, 0, 0), width=3)
        draw.text((x-20, 370), "TARGET", fill=(255, 0, 0))
        
        # Crosshair in center
        draw.line([(640, 200), (640, 520)], fill=(255, 255, 0), width=2)
        draw.line([(440, 360), (840, 360)], fill=(255, 255, 0), width=2)
        
        # Convert to JPEG bytes
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()

    async def start_live_stream(self, callback):
        """Start continuous live video stream (mock)"""
        print("📹 Starting live camera stream...")
        while True:
            frame = await self.get_camera_frame()
            await callback(frame)
            await asyncio.sleep(0.1)  # ~10 FPS for demo
