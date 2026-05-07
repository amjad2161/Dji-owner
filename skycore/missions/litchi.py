"""Litchi Mission Hub CSV import/export.

Litchi's standard CSV has 39 columns. This module handles round-trip
conversion between SkyCore WaypointMission and Litchi CSV so missions
planned in either tool can run on the other.

Schema reference (Litchi v4):
    latitude,longitude,altitude(m),heading(deg),curvesize(m),rotationdir,
    gimbalmode,gimbalpitchangle,actiontype1..15,actionparam1..15,
    altitudemode,speed(m/s),poi_latitude,poi_longitude,poi_altitude(m),
    poi_altitudemode,photo_timeinterval,photo_distinterval
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from skycore.core.types import GeoPoint, MissionStep
from skycore.missions.waypoint import WaypointMission

_LITCHI_HEADER = (
    "latitude,longitude,altitude(m),heading(deg),curvesize(m),rotationdir,"
    "gimbalmode,gimbalpitchangle,"
    + ",".join(f"actiontype{i},actionparam{i}" for i in range(1, 16))
    + ",altitudemode,speed(m/s),poi_latitude,poi_longitude,poi_altitude(m),"
    "poi_altitudemode,photo_timeinterval,photo_distinterval"
).split(",")

_ACTION_MAP = {
    "take_photo": (1, 0),
    "start_record": (2, 0),
    "stop_record": (3, 0),
}
_ACTION_REVERSE = {v[0]: k for k, v in _ACTION_MAP.items()}


def export_litchi_csv(
    mission: WaypointMission,
    path: Path | str,
    poi: Optional[GeoPoint] = None,
) -> None:
    """Write a SkyCore mission as a Litchi-compatible CSV."""
    p = Path(path)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(_LITCHI_HEADER)
        for step in mission.steps:
            row = [
                f"{step.target.lat:.6f}",
                f"{step.target.lon:.6f}",
                f"{step.target.alt:.1f}",
                f"{step.yaw_deg or 0:.1f}",
                "15",  # curvesize
                "0",   # rotationdir
                "2" if poi is not None else "0",  # gimbalmode: 2=focus POI
                f"{step.gimbal_pitch_deg or 0:.1f}",
            ]
            actions = list(step.actions)
            for slot in range(15):
                if slot < len(actions) and actions[slot] in _ACTION_MAP:
                    t, p_v = _ACTION_MAP[actions[slot]]
                    row.extend([str(t), str(p_v)])
                else:
                    row.extend(["-1", "0"])
            row.extend(
                [
                    "0",  # altitudemode
                    f"{step.speed_mps:.2f}",
                    f"{poi.lat if poi else 0:.6f}",
                    f"{poi.lon if poi else 0:.6f}",
                    f"{poi.alt if poi else 0:.1f}",
                    "0",  # poi altitudemode
                    "-1",  # photo_timeinterval
                    "-1",  # photo_distinterval
                ]
            )
            w.writerow(row)


def import_litchi_csv(path: Path | str, name: Optional[str] = None) -> WaypointMission:
    """Load a Litchi CSV into a SkyCore mission."""
    p = Path(path)
    mission = WaypointMission(name=name or p.stem)
    with p.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            actions = []
            for i in range(1, 16):
                t = int(row.get(f"actiontype{i}", "-1") or "-1")
                if t in _ACTION_REVERSE:
                    actions.append(_ACTION_REVERSE[t])
            mission.append(
                MissionStep(
                    target=GeoPoint(
                        lat=float(row["latitude"]),
                        lon=float(row["longitude"]),
                        alt=float(row["altitude(m)"]),
                    ),
                    speed_mps=float(row.get("speed(m/s)", 5.0) or 5.0),
                    yaw_deg=float(row.get("heading(deg)", 0) or 0),
                    gimbal_pitch_deg=float(row.get("gimbalpitchangle", 0) or 0),
                    actions=actions,
                )
            )
    return mission
