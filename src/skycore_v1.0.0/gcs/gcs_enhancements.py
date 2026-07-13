"""
SkyCore Ground Control Station Enhancement
Based on QGC/GCS best practices - real-time control, monitoring, and analysis

Features:
- Real-time telemetry display
- Parameter editor (like QGroundControl)
- Flight analysis (vibration, spectral density)
- Map integration with multiple providers
- Log file analysis
"""

import time
import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import deque
import numpy as np


@dataclass
class TelemetryPlotData:
    """Data for real-time plotting"""
    timestamps: deque
    values: deque
    min_val: float
    max_val: float
    
    def __init__(self, maxlen: int = 200):
        self.timestamps = deque(maxlen=maxlen)
        self.values = deque(maxlen=maxlen)
        self.min_val = float('inf')
        self.max_val = float('-inf')
        
    def add(self, timestamp: float, value: float):
        self.timestamps.append(timestamp)
        self.values.append(value)
        self.min_val = min(self.min_val, value)
        self.max_val = max(self.max_val, value)
        
    def get_range(self) -> Tuple[float, float]:
        """Get value range with padding"""
        padding = (self.max_val - self.min_val) * 0.1
        return self.min_val - padding, self.max_val + padding


class RealTimePlot:
    """
    Real-time plotting for telemetry data
    Similar to QGroundControl plots
    """
    
    PLOT_COLORS = [
        "#00ff88",  # green
        "#00d4ff",  # cyan
        "#ffaa00",  # orange
        "#ff4444",  # red
        "#aa44ff",  # purple
        "#44ffaa"   # teal
    ]
    
    def __init__(self, title: str = "", max_points: int = 200):
        self.title = title
        self.max_points = max_points
        self.series: Dict[str, TelemetryPlotData] = {}
        self.colors: Dict[str, str] = {}
        
    def add_series(self, name: str, color: Optional[str] = None):
        """Add new data series"""
        self.series[name] = TelemetryPlotData(maxlen=self.max_points)
        if color is None:
            color = self.PLOT_COLORS[len(self.series) % len(self.PLOT_COLORS)]
        self.colors[name] = color
        
    def add_point(self, series_name: str, timestamp: float, value: float):
        """Add data point to series"""
        if series_name not in self.series:
            self.add_series(series_name)
        self.series[series_name].add(timestamp, value)
        
    def render(self, canvas_width: int, canvas_height: int) -> List[Dict]:
        """
        Render plot to canvas coordinates
        Returns list of line segments to draw
        """
        if not self.series:
            return []
            
        # Find time range
        all_times = []
        for series in self.series.values():
            all_times.extend(list(series.timestamps))
            
        if not all_times:
            return []
            
        time_min = min(all_times)
        time_max = max(all_times)
        time_range = time_max - time_min if time_max > time_min else 1
        
        # Find value range across all series
        val_min = float('inf')
        val_max = float('-inf')
        for series in self.series.values():
            val_min = min(val_min, series.min_val)
            val_max = max(val_max, series.max_val)
            
        val_range = val_max - val_min if val_max > val_min else 1
        val_range = max(val_range, 0.1)  # Prevent division by zero
        
        padding = 0.1
        val_min -= val_range * padding
        val_max += val_range * padding
        val_range = val_max - val_min
        
        # Generate line segments
        lines = []
        for series_name, series in self.series.items():
            color = self.colors[series_name]
            
            if len(series.timestamps) < 2:
                continue
                
            points = []
            for t, v in zip(series.timestamps, series.values):
                x = ((t - time_min) / time_range) * canvas_width
                y = canvas_height - ((v - val_min) / val_range) * canvas_height
                points.append((x, y))
                
            # Create line segments
            for i in range(len(points) - 1):
                lines.append({
                    "x1": points[i][0],
                    "y1": points[i][1],
                    "x2": points[i+1][0],
                    "y2": points[i+1][1],
                    "color": color,
                    "width": 2
                })
                
        return lines


class ParameterManager:
    """
    Parameter management similar to QGroundControl
    Supports read/write, defaults, and metadata
    """
    
    # Common ArduPilot/PX4 parameters with metadata
    PARAM_METADATA = {
        "ARMD_CHECK": {
            "name": "ARMING_CHECK",
            "type": "int32",
            "default": 1,
            "min": 0,
            "max": 1,
            "description": "Arming check (0=disabled, 1=enabled)"
        },
        "PSC_ACCZ_P": {
            "name": "Accel Z PID",
            "type": "float",
            "default": 0.5,
            "min": 0,
            "max": 5,
            "description": "Vertical acceleration P gain"
        },
        "ATC_ACCEL_P": {
            "name": "Accel P",
            "type": "float",
            "default": 0.5,
            "min": 0,
            "max": 10,
            "description": "Acceleration P gain"
        },
        "GPS_POS_X": {
            "name": "GPS X offset",
            "type": "float",
            "default": 0.0,
            "min": -1,
            "max": 1,
            "description": "GPS position X offset (m)"
        },
        " EK3_AID_MASK": {
            "name": "GPS use",
            "type": "int32",
            "default": 7,
            "min": 0,
            "max": 7,
            "description": "GPS measurement use mask (bitfield)"
        }
    }
    
    def __init__(self):
        self.parameters: Dict[str, float] = {}
        self.defaults: Dict[str, float] = {}
        self.changes: List[Dict] = []  # History of changes
        
        # Initialize with defaults
        for param_name, meta in self.PARAM_METADATA.items():
            self.defaults[param_name] = meta["default"]
            self.parameters[param_name] = meta["default"]
            
    def get(self, name: str) -> Optional[float]:
        """Get parameter value"""
        return self.parameters.get(name)
        
    def set(self, name: str, value: float) -> bool:
        """Set parameter value"""
        if name not in self.PARAM_METADATA:
            return False
            
        meta = self.PARAM_METADATA[name]
        
        # Validate range
        if "min" in meta and value < meta["min"]:
            return False
        if "max" in meta and value > meta["max"]:
            return False
            
        # Record change
        old_value = self.parameters.get(name)
        self.parameters[name] = value
        self.changes.append({
            "name": name,
            "old_value": old_value,
            "new_value": value,
            "timestamp": time.time()
        })
        
        return True
        
    def reset_to_default(self, name: str) -> bool:
        """Reset parameter to default value"""
        if name in self.defaults:
            return self.set(name, self.defaults[name])
        return False
        
    def reset_all(self):
        """Reset all parameters to defaults"""
        for name, default in self.defaults.items():
            self.parameters[name] = default
            
    def export_params(self) -> List[Dict]:
        """Export all parameters"""
        return [
            {
                "name": name,
                "value": value,
                "default": self.defaults.get(name),
                "changed": value != self.defaults.get(name)
            }
            for name, value in self.parameters.items()
        ]
        
    def import_params(self, params: List[Dict]):
        """Import parameters from list"""
        for param in params:
            name = param.get("name")
            value = param.get("value")
            if name and value is not None:
                self.set(name, float(value))


class FlightAnalyzer:
    """
    Analyze flight logs for issues and performance
    Similar to ArduPilot's flight analysis tools
    """
    
    def __init__(self):
        self.data: Dict[str, List[float]] = {}
        
    def load_log(self, log_data: Dict[str, List[float]]):
        """Load flight log data"""
        self.data = log_data
        
    def analyze_vibrations(self) -> Dict:
        """
        Analyze vibration levels
        High vibrations indicate issues
        """
        if "vibration_x" not in self.data:
            return {"status": "no_data"}
            
        vib_x = np.array(self.data.get("vibration_x", [0]))
        vib_y = np.array(self.data.get("vibration_y", [0]))
        vib_z = np.array(self.data.get("vibration_z", [0]))
        
        # Calculate statistics
        stats = {
            "x": {
                "mean": np.mean(vib_x),
                "max": np.max(vib_x),
                "std": np.std(vib_x)
            },
            "y": {
                "mean": np.mean(vib_y),
                "max": np.max(vib_y),
                "std": np.std(vib_y)
            },
            "z": {
                "mean": np.mean(vib_z),
                "max": np.max(vib_z),
                "std": np.std(vib_z)
            }
        }
        
        # Determine status
        max_vib = max(stats["x"]["max"], stats["y"]["max"], stats["z"]["max"])
        if max_vib > 30:
            stats["status"] = "CRITICAL"
            stats["issue"] = "Very high vibrations detected"
        elif max_vib > 15:
            stats["status"] = "WARNING"
            stats["issue"] = "Elevated vibration levels"
        else:
            stats["status"] = "OK"
            
        return stats
        
    def analyze_spectral_density(self, signal_name: str) -> Dict:
        """
        Calculate power spectral density
        Useful for identifying resonance issues
        """
        if signal_name not in self.data:
            return {"status": "no_data"}
            
        signal = np.array(self.data[signal_name])
        
        # Simple FFT (in real impl, use scipy)
        n = len(signal)
        fft = np.fft.fft(signal)
        power = np.abs(fft[:n//2])**2
        freqs = np.fft.fftfreq(n)[:n//2]
        
        # Find dominant frequency
        if len(power) > 0:
            dominant_idx = np.argmax(power[1:]) + 1
            dominant_freq = abs(freqs[dominant_idx])
        else:
            dominant_freq = 0
            
        return {
            "dominant_frequency": dominant_freq,
            "total_power": np.sum(power),
            "peak_power": np.max(power)
        }
        
    def analyze_gps_glitches(self) -> Dict:
        """Analyze GPS data for glitches"""
        if "gps_lat" not in self.data:
            return {"status": "no_data"}
            
        lat = np.array(self.data.get("gps_lat", [0]))
        lon = np.array(self.data.get("gps_lon", [0]))
        
        # Calculate velocity
        if len(lat) > 1:
            d_lat = np.diff(lat)
            d_lon = np.diff(lon)
            speed = np.sqrt(d_lat**2 + d_lon**2) * 111000  # Rough m/s
            
            # Detect spikes (glitches)
            mean_speed = np.mean(speed)
            std_speed = np.std(speed)
            threshold = mean_speed + 3 * std_speed
            glitches = np.sum(speed > threshold)
            
            return {
                "glitch_count": int(glitches),
                "max_speed_mps": np.max(speed),
                "mean_speed_mps": mean_speed,
                "status": "WARNING" if glitches > 5 else "OK"
            }
            
        return {"status": "insufficient_data"}
        
    def generate_report(self) -> str:
        """Generate comprehensive analysis report"""
        report = []
        report.append("=" * 50)
        report.append("FLIGHT ANALYSIS REPORT")
        report.append("=" * 50)
        
        # Vibrations
        vib = self.analyze_vibrations()
        report.append(f"\nVibrations: {vib.get('status', 'unknown')}")
        if "x" in vib:
            report.append(f"  X: {vib['x']['mean']:.2f} (max: {vib['x']['max']:.2f})")
            report.append(f"  Y: {vib['y']['mean']:.2f} (max: {vib['y']['max']:.2f})")
            report.append(f"  Z: {vib['z']['mean']:.2f} (max: {vib['z']['max']:.2f})")
            
        # GPS
        gps = self.analyze_gps_glitches()
        report.append(f"\nGPS: {gps.get('status', 'unknown')}")
        if "glitch_count" in gps:
            report.append(f"  Glitches: {gps['glitch_count']}")
            report.append(f"  Mean speed: {gps.get('mean_speed_mps', 0):.1f} m/s")
            
        report.append("\n" + "=" * 50)
        return "\n".join(report)


class MapTileProvider:
    """
    Map tile provider for GCS
    Supports multiple tile sources
    """
    
    PROVIDERS = {
        "osm": {
            "name": "OpenStreetMap",
            "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "attribution": "© OpenStreetMap contributors"
        },
        "satellite": {
            "name": "ESRI Satellite",
            "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            "attribution": "© ESRI"
        },
        "terrain": {
            "name": "Terrain",
            "url": "https://tile.opentopomap.org/{z}/{x}/{y}.png",
            "attribution": "© OpenTopoMap"
        }
    }
    
    def __init__(self, provider: str = "osm"):
        self.provider = provider
        self.tiles: Dict[str, object] = {}  # Cache
        
    def get_tile_url(self, x: int, y: int, z: int) -> str:
        """Get URL for tile at given coordinates"""
        if self.provider not in self.PROVIDERS:
            self.provider = "osm"
            
        template = self.PROVIDERS[self.provider]["url"]
        return template.format(x=x, y=y, z=z)
        
    def lat_lon_to_tile(self, lat: float, lon: float, zoom: int) -> Tuple[int, int]:
        """Convert lat/lon to tile coordinates"""
        import math
        
        lat_rad = math.radians(lat)
        n = 2.0 ** zoom
        
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        
        return x, y


# Example usage
if __name__ == "__main__":
    # Create real-time plot
    plot = RealTimePlot("Telemetry", max_points=200)
    plot.add_series("Altitude", "#00ff88")
    plot.add_series("Target Alt", "#00d4ff")
    
    # Simulate data
    start_time = time.time()
    for i in range(100):
        t = time.time() - start_time
        plot.add_point("Altitude", t, 20 + 5 * math.sin(i / 10))
        plot.add_point("Target Alt", t, 20)
        
    lines = plot.render(800, 300)
    print(f"Generated {len(lines)} line segments")
    
    # Parameter management
    params = ParameterManager()
    print(f"\nParameter ARMD_CHECK: {params.get('ARMD_CHECK')}")
    params.set('ARMD_CHECK', 0)
    print(f"After change: {params.get('ARMD_CHECK')}")
    
    # Flight analyzer
    analyzer = FlightAnalyzer()
    analyzer.load_log({
        "vibration_x": np.random.randn(100) * 5,
        "vibration_y": np.random.randn(100) * 5,
        "vibration_z": np.random.randn(100) * 10,
        "gps_lat": 32.0 + np.cumsum(np.random.randn(100) * 0.0001),
        "gps_lon": 34.0 + np.cumsum(np.random.randn(100) * 0.0001)
    })
    
    vib_report = analyzer.analyze_vibrations()
    print(f"\nVibration status: {vib_report.get('status')}")
    
    # Map tiles
    map_provider = MapTileProvider("satellite")
    tile_url = map_provider.get_tile_url(17125, 11184, 15)
    print(f"\nMap tile URL: {tile_url}")