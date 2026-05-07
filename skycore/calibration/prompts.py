"""Calibration reminders.

A pre-flight nag system that surfaces calibration tasks the pilot likely
should do before flight, based on conditions like firmware change, large
geographic move, recent crash, or compass interference indicators.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CalibrationLevel(str, Enum):
    INFO = "info"
    RECOMMENDED = "recommended"
    REQUIRED = "required"


@dataclass
class CalibrationPrompt:
    name: str
    level: CalibrationLevel
    reason: str
    procedure: str


@dataclass
class DroneState:
    """Inputs to the calibration heuristic."""

    last_compass_calibration_lat: Optional[float] = None
    last_compass_calibration_lon: Optional[float] = None
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    firmware_version: Optional[str] = None
    last_firmware_calibrated: Optional[str] = None
    days_since_imu_calibration: Optional[int] = None
    crashed_recently: bool = False
    propellers_replaced: bool = False
    near_metal_structure: bool = False  # interference check


def needed_calibrations(state: DroneState) -> list[CalibrationPrompt]:
    out: list[CalibrationPrompt] = []

    # Compass after geographic move
    if (state.last_compass_calibration_lat is not None
            and state.current_lat is not None
            and state.last_compass_calibration_lon is not None
            and state.current_lon is not None):
        d_km = _haversine_km(
            state.last_compass_calibration_lat, state.last_compass_calibration_lon,
            state.current_lat, state.current_lon,
        )
        if d_km > 100:
            out.append(CalibrationPrompt(
                name="Compass",
                level=CalibrationLevel.REQUIRED,
                reason=f"Moved {d_km:.0f} km since last calibration",
                procedure="Hold drone level, rotate 360° horizontally, then 360° vertically. Stay clear of metal.",
            ))

    # Compass after metal interference
    if state.near_metal_structure:
        out.append(CalibrationPrompt(
            name="Compass",
            level=CalibrationLevel.RECOMMENDED,
            reason="Operating near metal structure / vehicles",
            procedure="Move at least 10 m from metal, then re-check compass interference indicator.",
        ))

    # IMU after firmware update
    if (state.firmware_version is not None
            and state.firmware_version != state.last_firmware_calibrated):
        out.append(CalibrationPrompt(
            name="IMU",
            level=CalibrationLevel.RECOMMENDED,
            reason=f"Firmware changed to {state.firmware_version}",
            procedure="Place drone on a level surface, run IMU calibration in DJI Assistant 2 / DJI Fly settings.",
        ))

    # IMU after long inactivity
    if state.days_since_imu_calibration is not None and state.days_since_imu_calibration > 90:
        out.append(CalibrationPrompt(
            name="IMU",
            level=CalibrationLevel.INFO,
            reason=f"IMU not calibrated for {state.days_since_imu_calibration} days",
            procedure="Quarterly IMU re-calibration is good practice.",
        ))

    # Vision sensors after crash
    if state.crashed_recently:
        out.append(CalibrationPrompt(
            name="Vision sensors",
            level=CalibrationLevel.REQUIRED,
            reason="Recent crash detected",
            procedure="Inspect cameras, run vision sensor calibration in DJI Assistant 2.",
        ))

    # Propeller balance after replacement
    if state.propellers_replaced:
        out.append(CalibrationPrompt(
            name="Propeller balance",
            level=CalibrationLevel.RECOMMENDED,
            reason="Propellers replaced",
            procedure="Test hover at 2 m for 30 sec; review log for vibration spikes.",
        ))

    return out


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
