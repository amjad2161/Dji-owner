"""
SkyCore Profiles - Drone Models
==============================
Known specs for 12+ current drone models.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger(__name__)


@dataclass
class DroneProfile:
    """Drone model profile."""
    name: str
    manufacturer: str
    series: str
    
    # Dimensions
    dimensions_mm: Dict[str, float]  # length, width, height
    weight_kg: float
    
    # Flight specs
    max_speed_horizontal_kmh: float
    max_speed_vertical_kmh: float
    max_altitude_m: float
    max_wind_resistance_kmh: float
    
    # Battery
    battery_capacity_mah: int
    battery_voltage: float
    battery_energy_wh: float
    max_flight_time_min: int
    
    # Camera specs
    camera_sensor: str
    camera_resolution_mp: float
    video_resolution: str
    gimbal_stabilization: str
    
    # Connectivity
    transmission_system: str
    transmission_range_km: float
    
    # Safety
    obstacle_sensing_range_m: float
    has_adsb: bool
    has_rtk: bool
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'manufacturer': self.manufacturer,
            'series': self.series,
            'dimensions_mm': self.dimensions_mm,
            'weight_kg': self.weight_kg,
            'max_speed_horizontal_kmh': self.max_speed_horizontal_kmh,
            'max_speed_vertical_kmh': self.max_speed_vertical_kmh,
            'max_altitude_m': self.max_altitude_m,
            'max_wind_resistance_kmh': self.max_wind_resistance_kmh,
            'battery': {
                'capacity_mah': self.battery_capacity_mah,
                'voltage': self.battery_voltage,
                'energy_wh': self.battery_energy_wh
            },
            'flight_time_min': self.max_flight_time_min,
            'camera': {
                'sensor': self.camera_sensor,
                'resolution_mp': self.camera_resolution_mp,
                'video_resolution': self.video_resolution,
                'gimbal': self.gimbal_stabilization
            },
            'transmission': {
                'system': self.transmission_system,
                'range_km': self.transmission_range_km
            },
            'safety': {
                'obstacle_sensing_m': self.obstacle_sensing_range_m,
                'adsb': self.has_adsb,
                'rtk': self.has_rtk
            }
        }


# Pre-defined profiles for common drone models
PROFILES: Dict[str, DroneProfile] = {
    "Mavic 3 Pro": DroneProfile(
        name="Mavic 3 Pro",
        manufacturer="DJI",
        series="Mavic 3",
        dimensions_mm={'length': 347.5, 'width': 290.8, 'height': 107.7},
        weight_kg=958,
        max_speed_horizontal_kmh=75,
        max_speed_vertical_kmh=6,
        max_altitude_m=6000,
        max_wind_resistance_kmh=43.2,  # 12 m/s
        battery_capacity_mah=5880,
        battery_voltage=15.4,
        battery_energy_wh=77,
        max_flight_time_min=43,
        camera_sensor="Hasselblad L-Format",
        camera_resolution_mp=20.0,
        video_resolution="5.1K/50fps, 4K/120fps",
        gimbal_stabilization="3-axis mechanical",
        transmission_system="OcuSync 4",
        transmission_range_km=15,
        obstacle_sensing_range_m=200,
        has_adsb=True,
        has_rtk=True
    ),
    
    "Mavic 3": DroneProfile(
        name="Mavic 3",
        manufacturer="DJI",
        series="Mavic 3",
        dimensions_mm={'length': 347.5, 'width': 290.8, 'height': 107.7},
        weight_kg=895,
        max_speed_horizontal_kmh=75,
        max_speed_vertical_kmh=6,
        max_altitude_m=6000,
        max_wind_resistance_kmh=43.2,
        battery_capacity_mah=5000,
        battery_voltage=15.4,
        battery_energy_wh=77,
        max_flight_time_min=46,
        camera_sensor="4/3 CMOS",
        camera_resolution_mp=20.0,
        video_resolution="5.1K/50fps, 4K/120fps",
        gimbal_stabilization="3-axis mechanical",
        transmission_system="OcuSync 4",
        transmission_range_km=15,
        obstacle_sensing_range_m=200,
        has_adsb=True,
        has_rtk=True
    ),
    
    "Mavic 3 Classic": DroneProfile(
        name="Mavic 3 Classic",
        manufacturer="DJI",
        series="Mavic 3",
        dimensions_mm={'length': 347.5, 'width': 290.8, 'height': 107.7},
        weight_kg=895,
        max_speed_horizontal_kmh=75,
        max_speed_vertical_kmh=6,
        max_altitude_m=6000,
        max_wind_resistance_kmh=43.2,
        battery_capacity_mah=5000,
        battery_voltage=15.4,
        battery_energy_wh=77,
        max_flight_time_min=46,
        camera_sensor="4/3 CMOS",
        camera_resolution_mp=20.0,
        video_resolution="5.1K/50fps, 4K/120fps",
        gimbal_stabilization="3-axis mechanical",
        transmission_system="OcuSync 4",
        transmission_range_km=15,
        obstacle_sensing_range_m=200,
        has_adsb=True,
        has_rtk=True
    ),
    
    "Mavic Air 2S": DroneProfile(
        name="Mavic Air 2S",
        manufacturer="DJI",
        series="Mavic Air",
        dimensions_mm={'length': 253, 'width': 289, 'height': 77},
        weight_kg=595,
        max_speed_horizontal_kmh=68.4,
        max_speed_vertical_kmh=6,
        max_altitude_m=5000,
        max_wind_resistance_kmh=37.8,
        battery_capacity_mah=3750,
        battery_voltage=13.2,
        battery_energy_wh=40.84,
        max_flight_time_min=31,
        camera_sensor="1-inch CMOS",
        camera_resolution_mp=20.0,
        video_resolution="5.4K/30fps, 4K/60fps",
        gimbal_stabilization="3-axis mechanical",
        transmission_system="OcuSync 3",
        transmission_range_km=12,
        obstacle_sensing_range_m=49,
        has_adsb=True,
        has_rtk=False
    ),
    
    "Mavic Air 2": DroneProfile(
        name="Mavic Air 2",
        manufacturer="DJI",
        series="Mavic Air",
        dimensions_mm={'length': 253, 'width': 289, 'height': 77},
        weight_kg=570,
        max_speed_horizontal_kmh=68.4,
        max_speed_vertical_kmh=4,
        max_altitude_m=5000,
        max_wind_resistance_kmh=29,
        battery_capacity_mah=3500,
        battery_voltage=11.55,
        battery_energy_wh=40.42,
        max_flight_time_min=34,
        camera_sensor="1/2-inch CMOS",
        camera_resolution_mp=48.0,
        video_resolution="4K/60fps",
        gimbal_stabilization="3-axis mechanical",
        transmission_system="OcuSync 2",
        transmission_range_km=10,
        obstacle_sensing_range_m=40,
        has_adsb=False,
        has_rtk=False
    ),
    
    "Mini 3 Pro": DroneProfile(
        name="Mini 3 Pro",
        manufacturer="DJI",
        series="Mini",
        dimensions_mm={'length': 248, 'width': 289, 'height': 62},
        weight_kg=0.249,  # Under 250g
        max_speed_horizontal_kmh=57.6,
        max_speed_vertical_kmh=5,
        max_altitude_m=4000,
        max_wind_resistance_kmh=29,
        battery_capacity_mah=2453,
        battery_voltage=7.38,
        battery_energy_wh=18.1,
        max_flight_time_min=34,
        camera_sensor="1/1.3-inch CMOS",
        camera_resolution_mp=48.0,
        video_resolution="4K/60fps",
        gimbal_stabilization="3-axis mechanical",
        transmission_system="OcuSync 3",
        transmission_range_km=12,
        obstacle_sensing_range_m=12,
        has_adsb=False,
        has_rtk=False
    ),
    
    "Mini 2": DroneProfile(
        name="Mini 2",
        manufacturer="DJI",
        series="Mini",
        dimensions_mm={'length': 249, 'width': 289, 'height': 56},
        weight_kg=0.249,
        max_speed_horizontal_kmh=57.6,
        max_speed_vertical_kmh=3,
        max_altitude_m=4000,
        max_wind_resistance_kmh=29,
        battery_capacity_mah=2250,
        battery_voltage=7.7,
        battery_energy_wh=17.32,
        max_flight_time_min=31,
        camera_sensor="1/2.3-inch CMOS",
        camera_resolution_mp=12.0,
        video_resolution="4K/30fps",
        gimbal_stabilization="3-axis mechanical",
        transmission_system="OcuSync 2",
        transmission_range_km=10,
        obstacle_sensing_range_m=5,
        has_adsb=False,
        has_rtk=False
    ),
    
    "Mavic 2 Pro": DroneProfile(
        name="Mavic 2 Pro",
        manufacturer="DJI",
        series="Mavic 2",
        dimensions_mm={'length': 322, 'width': 242, 'height': 84},
        weight_kg=907,
        max_speed_horizontal_kmh=72,
        max_speed_vertical_kmh=5,
        max_altitude_m=6000,
        max_wind_resistance_kmh=38,
        battery_capacity_mah=3850,
        battery_voltage=15.4,
        battery_energy_wh=59.29,
        max_flight_time_min=31,
        camera_sensor="1-inch CMOS",
        camera_resolution_mp=20.0,
        video_resolution="4K/30fps",
        gimbal_stabilization="3-axis mechanical",
        transmission_system="OcuSync 2",
        transmission_range_km=8,
        obstacle_sensing_range_m=40,
        has_adsb=False,
        has_rtk=True
    ),
    
    "Mavic 2 Zoom": DroneProfile(
        name="Mavic 2 Zoom",
        manufacturer="DJI",
        series="Mavic 2",
        dimensions_mm={'length': 322, 'width': 242, 'height': 84},
        weight_kg=905,
        max_speed_horizontal_kmh=72,
        max_speed_vertical_kmh=5,
        max_altitude_m=6000,
        max_wind_resistance_kmh=38,
        battery_capacity_mah=3850,
        battery_voltage=15.4,
        battery_energy_wh=59.29,
        max_flight_time_min=31,
        camera_sensor="1/2.3-inch CMOS",
        camera_resolution_mp=12.0,
        video_resolution="4K/30fps",
        gimbal_stabilization="3-axis mechanical",
        transmission_system="OcuSync 2",
        transmission_range_km=8,
        obstacle_sensing_range_m=40,
        has_adsb=False,
        has_rtk=False
    ),
    
    "Phantom 4 Pro V2.0": DroneProfile(
        name="Phantom 4 Pro V2.0",
        manufacturer="DJI",
        series="Phantom",
        dimensions_mm={'length': 350, 'width': 350, 'height': 197},
        weight_kg=1375,
        max_speed_horizontal_kmh=72,
        max_speed_vertical_kmh=6,
        max_altitude_m=6000,
        max_wind_resistance_kmh=44,
        battery_capacity_mah=5870,
        battery_voltage=15.4,
        battery_energy_wh=89.2,
        max_flight_time_min=30,
        camera_sensor="1-inch CMOS",
        camera_resolution_mp=20.0,
        video_resolution="4K/60fps",
        gimbal_stabilization="3-axis mechanical",
        transmission_system="OcuSync 2",
        transmission_range_km=8,
        obstacle_sensing_range_m=40,
        has_adsb=False,
        has_rtk=True
    ),
    
    "Inspire 3": DroneProfile(
        name="Inspire 3",
        manufacturer="DJI",
        series="Inspire",
        dimensions_mm={'length': 946, 'width': 709, 'height': 376},
        weight_kg=3.99,
        max_speed_horizontal_kmh=94,
        max_speed_vertical_kmh=8,
        max_altitude_m=8000,
        max_wind_resistance_kmh=50,
        battery_capacity_mah=5880,
        battery_voltage=26.4,
        battery_energy_wh=153.9,
        max_flight_time_min=28,
        camera_sensor="Full-frame",
        camera_resolution_mp=45.0,
        video_resolution="8K/25fps, 4K/120fps",
        gimbal_stabilization="3-axis mechanical",
        transmission_system="OcuSync 3 Pro",
        transmission_range_km=15,
        obstacle_sensing_range_m=90,
        has_adsb=True,
        has_rtk=True
    ),
    
    "Tello": DroneProfile(
        name="Tello",
        manufacturer="DJI (Ryze)",
        series="Tello",
        dimensions_mm={'length': 98, 'width': 92.5, 'height': 41},
        weight_kg=0.080,
        max_speed_horizontal_kmh=28.8,
        max_speed_vertical_kmh=3,
        max_altitude_m=100,
        max_wind_resistance_kmh=10,
        battery_capacity_mah=1100,
        battery_voltage=3.8,
        battery_energy_wh=4.18,
        max_flight_time_min=13,
        camera_sensor="1/5-inch CMOS",
        camera_resolution_mp=5.0,
        video_resolution="720P/30fps",
        gimbal_stabilization="Electronic",
        transmission_system="WiFi",
        transmission_range_km=0.1,
        obstacle_sensing_range_m=0,
        has_adsb=False,
        has_rtk=False
    )
}


def get_profile(name: str) -> Optional[DroneProfile]:
    """Get drone profile by name."""
    return PROFILES.get(name)


def list_profiles() -> List[str]:
    """List all available profile names."""
    return list(PROFILES.keys())


def get_profiles_by_series(series: str) -> List[DroneProfile]:
    """Get profiles by series."""
    return [p for p in PROFILES.values() if p.series.lower() in series.lower()]


# Export
__all__ = ['DroneProfile', 'PROFILES', 'get_profile', 'list_profiles', 'get_profiles_by_series']