"""Drone hardware profiles.

Known specs for current and recent DJI Mavic models, used to set
safety defaults and surface the right limits in the UI.

Where DJI publishes officially conflicting numbers (e.g. between marketing
and spec sheet), we follow the spec sheet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DroneProfile:
    model: str
    family: str  # "mavic-3", "air", "mini", "mavic-2", "enterprise"
    weight_g: int
    max_horiz_speed_mps: float
    max_ascent_mps: float
    max_descent_mps: float
    max_wind_resistance_mps: float
    max_flight_time_min: int
    max_altitude_m: int  # service ceiling above sea level
    has_obstacle_sensing: bool
    has_d_log: bool
    camera_sensor: str = ""
    max_video_resolution: str = ""
    max_bitrate_mbps: int = 0
    transmission: str = ""  # OcuSync version
    sdk_support: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    @property
    def max_wind_resistance_kph(self) -> float:
        return self.max_wind_resistance_mps * 3.6


_PROFILES: dict[str, DroneProfile] = {
    p.model.lower(): p
    for p in [
        DroneProfile(
            model="Mavic 3 Pro",
            family="mavic-3",
            weight_g=958,
            max_horiz_speed_mps=21.0,
            max_ascent_mps=8.0,
            max_descent_mps=6.0,
            max_wind_resistance_mps=12.0,
            max_flight_time_min=43,
            max_altitude_m=6000,
            has_obstacle_sensing=True,
            has_d_log=True,
            camera_sensor="4/3 CMOS Hasselblad + 70mm + 166mm",
            max_video_resolution="5.1K @ 50fps",
            max_bitrate_mbps=200,
            transmission="O3+",
            sdk_support=("MSDK V5",),
        ),
        DroneProfile(
            model="Mavic 3",
            family="mavic-3",
            weight_g=895,
            max_horiz_speed_mps=21.0,
            max_ascent_mps=8.0,
            max_descent_mps=6.0,
            max_wind_resistance_mps=12.0,
            max_flight_time_min=46,
            max_altitude_m=6000,
            has_obstacle_sensing=True,
            has_d_log=True,
            camera_sensor="4/3 CMOS Hasselblad",
            max_video_resolution="5.1K @ 50fps",
            max_bitrate_mbps=200,
            transmission="O3+",
            sdk_support=("MSDK V5",),
        ),
        DroneProfile(
            model="Mavic 3 Classic",
            family="mavic-3",
            weight_g=895,
            max_horiz_speed_mps=21.0,
            max_ascent_mps=8.0,
            max_descent_mps=6.0,
            max_wind_resistance_mps=12.0,
            max_flight_time_min=46,
            max_altitude_m=6000,
            has_obstacle_sensing=True,
            has_d_log=False,
            camera_sensor="4/3 CMOS Hasselblad",
            max_video_resolution="5.1K @ 50fps",
            max_bitrate_mbps=200,
            transmission="O3+",
            sdk_support=("MSDK V5",),
        ),
        DroneProfile(
            model="Mavic 3 Enterprise",
            family="enterprise",
            weight_g=915,
            max_horiz_speed_mps=21.0,
            max_ascent_mps=8.0,
            max_descent_mps=6.0,
            max_wind_resistance_mps=12.0,
            max_flight_time_min=45,
            max_altitude_m=6000,
            has_obstacle_sensing=True,
            has_d_log=True,
            camera_sensor="4/3 CMOS",
            max_video_resolution="4K @ 30fps",
            max_bitrate_mbps=130,
            transmission="O3 Enterprise",
            sdk_support=("MSDK V5", "PSDK"),
            notes="RTK accuracy, payload SDK",
        ),
        DroneProfile(
            model="Air 3",
            family="air",
            weight_g=720,
            max_horiz_speed_mps=21.0,
            max_ascent_mps=10.0,
            max_descent_mps=10.0,
            max_wind_resistance_mps=12.0,
            max_flight_time_min=46,
            max_altitude_m=6000,
            has_obstacle_sensing=True,
            has_d_log=True,  # D-Log M
            camera_sensor="1/1.3 CMOS dual",
            max_video_resolution="4K @ 100fps",
            max_bitrate_mbps=150,
            transmission="O4",
            sdk_support=("MSDK V5",),
        ),
        DroneProfile(
            model="Air 2S",
            family="air",
            weight_g=595,
            max_horiz_speed_mps=19.0,
            max_ascent_mps=6.0,
            max_descent_mps=6.0,
            max_wind_resistance_mps=10.7,
            max_flight_time_min=31,
            max_altitude_m=5000,
            has_obstacle_sensing=True,
            has_d_log=True,
            camera_sensor="1\" CMOS",
            max_video_resolution="5.4K @ 30fps",
            max_bitrate_mbps=150,
            transmission="O3",
            sdk_support=("MSDK V4 (legacy)",),
        ),
        DroneProfile(
            model="Mavic Air 2",
            family="air",
            weight_g=570,
            max_horiz_speed_mps=19.0,
            max_ascent_mps=4.0,
            max_descent_mps=3.0,
            max_wind_resistance_mps=8.5,
            max_flight_time_min=34,
            max_altitude_m=5000,
            has_obstacle_sensing=True,
            has_d_log=False,
            camera_sensor="1/2\" CMOS",
            max_video_resolution="4K @ 60fps",
            max_bitrate_mbps=120,
            transmission="OcuSync 2.0",
            sdk_support=("MSDK V4",),
        ),
        DroneProfile(
            model="Mini 4 Pro",
            family="mini",
            weight_g=249,
            max_horiz_speed_mps=16.0,
            max_ascent_mps=5.0,
            max_descent_mps=5.0,
            max_wind_resistance_mps=10.7,
            max_flight_time_min=34,
            max_altitude_m=4000,
            has_obstacle_sensing=True,
            has_d_log=True,  # D-Log M
            camera_sensor="1/1.3 CMOS",
            max_video_resolution="4K @ 100fps",
            max_bitrate_mbps=150,
            transmission="O4",
            sdk_support=("MSDK V5",),
        ),
        DroneProfile(
            model="Mini 3 Pro",
            family="mini",
            weight_g=249,
            max_horiz_speed_mps=16.0,
            max_ascent_mps=5.0,
            max_descent_mps=5.0,
            max_wind_resistance_mps=10.7,
            max_flight_time_min=34,
            max_altitude_m=4000,
            has_obstacle_sensing=True,
            has_d_log=False,
            camera_sensor="1/1.3 CMOS",
            max_video_resolution="4K @ 60fps",
            max_bitrate_mbps=150,
            transmission="O3",
            sdk_support=("MSDK V5",),
        ),
        DroneProfile(
            model="Mavic 2 Pro",
            family="mavic-2",
            weight_g=907,
            max_horiz_speed_mps=20.0,
            max_ascent_mps=5.0,
            max_descent_mps=3.0,
            max_wind_resistance_mps=10.0,
            max_flight_time_min=31,
            max_altitude_m=6000,
            has_obstacle_sensing=True,
            has_d_log=True,
            camera_sensor="1\" CMOS Hasselblad",
            max_video_resolution="4K @ 30fps",
            max_bitrate_mbps=100,
            transmission="OcuSync 2.0",
            sdk_support=("MSDK V4",),
            notes="Litchi works fully",
        ),
        DroneProfile(
            model="Mavic Pro",
            family="mavic-2",
            weight_g=734,
            max_horiz_speed_mps=18.0,
            max_ascent_mps=5.0,
            max_descent_mps=3.0,
            max_wind_resistance_mps=10.0,
            max_flight_time_min=27,
            max_altitude_m=5000,
            has_obstacle_sensing=True,
            has_d_log=False,
            camera_sensor="1/2.3\" CMOS",
            max_video_resolution="4K @ 30fps",
            max_bitrate_mbps=60,
            transmission="OcuSync 1.0",
            sdk_support=("MSDK V4 (legacy)",),
            notes="Litchi works fully",
        ),
        DroneProfile(
            model="Tello",
            family="educational",
            weight_g=80,
            max_horiz_speed_mps=8.0,
            max_ascent_mps=2.0,
            max_descent_mps=2.0,
            max_wind_resistance_mps=4.0,
            max_flight_time_min=13,
            max_altitude_m=30,
            has_obstacle_sensing=False,
            has_d_log=False,
            camera_sensor="5 MP",
            max_video_resolution="720p @ 30fps",
            max_bitrate_mbps=4,
            transmission="Wi-Fi",
            sdk_support=("Tello SDK",),
            notes="Indoor / educational",
        ),
    ]
}


def get_profile(model: str) -> Optional[DroneProfile]:
    """Look up a profile by model name (case-insensitive, exact or fuzzy)."""
    key = model.lower().strip()
    if key in _PROFILES:
        return _PROFILES[key]
    for k, p in _PROFILES.items():
        if key in k or k in key:
            return p
    return None


def all_profiles() -> list[DroneProfile]:
    return list(_PROFILES.values())
