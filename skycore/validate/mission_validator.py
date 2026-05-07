"""Mission validator. Pre-flight gate over geofence, airspace, terrain, energy.

Does everything you'd want before pressing takeoff: per-waypoint geofence
checks, airspace classification, terrain clearance, battery budget. Returns
a structured report you can render in the dashboard or block flight on.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from skycore.core.types import GeoPoint
from skycore.missions.waypoint import WaypointMission

log = logging.getLogger(__name__)


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass
class WaypointIssue:
    waypoint_index: int
    severity: Severity
    detail: str
    category: str = ""


@dataclass
class ValidationReport:
    mission_name: str = ""
    issues: list[WaypointIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == Severity.ERROR for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == Severity.WARN for i in self.issues) or bool(self.warnings)

    def to_dict(self) -> dict:
        return {
            "mission": self.mission_name,
            "valid": self.is_valid,
            "warnings": self.has_warnings,
            "issues": [
                {"waypoint": i.waypoint_index, "severity": i.severity.value, "detail": i.detail, "category": i.category}
                for i in self.issues
            ],
            "messages": self.warnings,
            "info": self.info,
        }

    def render(self) -> str:
        out = [f"Mission: {self.mission_name}"]
        for i in self.issues:
            glyph = {Severity.INFO: "i", Severity.WARN: "!", Severity.ERROR: "✗"}[i.severity]
            out.append(f"  {glyph} wp[{i.waypoint_index}] {i.category}: {i.detail}")
        for w in self.warnings:
            out.append(f"  ! {w}")
        for n in self.info:
            out.append(f"  i {n}")
        out.append(f"  Result: {'OK' if self.is_valid else 'BLOCKED'}")
        return "\n".join(out)


class MissionValidator:
    """Compose any subset of validation checks."""

    def __init__(
        self,
        geofence: Optional["PolygonGeofence"] = None,  # type: ignore  # noqa: F821
        circular_geofence: Optional["GeofenceConfig"] = None,  # type: ignore  # noqa: F821
        airspace_db: Optional["AirspaceDatabase"] = None,  # type: ignore  # noqa: F821
        terrain_clearance_m: Optional[float] = None,
        terrain_amsl_offset_m: float = 0.0,
        max_altitude_m: float = 120.0,
        drone_profile: Optional["DroneProfile"] = None,  # type: ignore  # noqa: F821
        battery_capacity_pct: Optional[float] = None,
    ):
        self.geofence = geofence
        self.circular_geofence = circular_geofence
        self.airspace_db = airspace_db
        self.terrain_clearance_m = terrain_clearance_m
        self.terrain_amsl_offset_m = terrain_amsl_offset_m
        self.max_altitude_m = max_altitude_m
        self.drone_profile = drone_profile
        self.battery_capacity_pct = battery_capacity_pct

    def validate(self, mission: WaypointMission) -> ValidationReport:
        report = ValidationReport(mission_name=mission.name)
        if not mission.steps:
            report.warnings.append("empty mission")
            return report

        for i, step in enumerate(mission.steps):
            self._check_altitude(report, i, step.target)
            self._check_geofence(report, i, step.target)
            self._check_circular_geofence(report, i, step.target)
            self._check_airspace(report, i, step.target)

        if self.terrain_clearance_m is not None:
            self._check_terrain(report, mission)

        if self.drone_profile and self.battery_capacity_pct is not None:
            self._check_battery_budget(report, mission)

        if self.drone_profile:
            self._check_speeds(report, mission)

        report.info.append(f"{len(mission.steps)} waypoints validated")
        return report

    # --- individual checks ---

    def _check_altitude(self, report, idx, point: GeoPoint):
        if point.alt > self.max_altitude_m:
            report.issues.append(WaypointIssue(
                idx, Severity.ERROR,
                f"altitude {point.alt:.1f} m exceeds max {self.max_altitude_m:.0f} m",
                category="altitude",
            ))
        elif point.alt < 0:
            report.issues.append(WaypointIssue(
                idx, Severity.ERROR, f"negative altitude {point.alt:.1f} m", category="altitude",
            ))

    def _check_geofence(self, report, idx, point: GeoPoint):
        if self.geofence is None:
            return
        try:
            if not self.geofence.contains(point):
                report.issues.append(WaypointIssue(
                    idx, Severity.ERROR,
                    f"outside polygon geofence '{self.geofence.name}'",
                    category="geofence",
                ))
        except Exception as e:
            report.warnings.append(f"polygon check failed for wp[{idx}]: {e}")

    def _check_circular_geofence(self, report, idx, point: GeoPoint):
        if not self.circular_geofence or not self.circular_geofence.home:
            return
        d = self.circular_geofence.home.haversine_m(point)
        if d > self.circular_geofence.max_radius_m:
            report.issues.append(WaypointIssue(
                idx, Severity.ERROR,
                f"{d:.0f} m from home > radius {self.circular_geofence.max_radius_m:.0f} m",
                category="geofence",
            ))

    def _check_airspace(self, report, idx, point: GeoPoint):
        if self.airspace_db is None:
            return
        try:
            critical, hits = self.airspace_db.is_critical_at(
                GeoPoint(point.lat, point.lon, point.alt + self.terrain_amsl_offset_m)
            )
            if critical:
                names = ", ".join(h.name for h in hits)
                report.issues.append(WaypointIssue(
                    idx, Severity.ERROR, f"enters critical airspace: {names}", category="airspace",
                ))
        except Exception as e:
            report.warnings.append(f"airspace check failed for wp[{idx}]: {e}")

    def _check_terrain(self, report, mission: WaypointMission):
        try:
            from skycore.terrain import get_elevations
            pts = [(s.target.lat, s.target.lon) for s in mission.steps]
            elevs = get_elevations(pts)
            for i, (s, e) in enumerate(zip(mission.steps, elevs)):
                amsl = s.target.alt + self.terrain_amsl_offset_m
                clearance = amsl - e
                if clearance < self.terrain_clearance_m:
                    report.issues.append(WaypointIssue(
                        i, Severity.ERROR,
                        f"terrain clearance {clearance:.1f} m < required {self.terrain_clearance_m:.0f} m",
                        category="terrain",
                    ))
        except Exception as e:
            report.warnings.append(f"terrain check skipped: {e}")

    def _check_speeds(self, report, mission: WaypointMission):
        max_speed = self.drone_profile.max_horiz_speed_mps
        for i, s in enumerate(mission.steps):
            if s.speed_mps > max_speed:
                report.issues.append(WaypointIssue(
                    i, Severity.WARN,
                    f"speed {s.speed_mps:.1f} m/s exceeds drone max {max_speed:.1f} m/s",
                    category="speed",
                ))

    def _check_battery_budget(self, report, mission: WaypointMission):
        try:
            from skycore.budget import estimate_mission_duration_s, estimate_battery_consumption_pct
            duration_s = estimate_mission_duration_s(mission)
            consumed = estimate_battery_consumption_pct(
                mission, self.drone_profile, headwind_kph=0
            )
            available = self.battery_capacity_pct
            margin = available - consumed
            report.info.append(
                f"estimated: duration {duration_s/60:.1f} min, battery use {consumed:.0f}% (available {available:.0f}%)"
            )
            if margin < 20:
                report.issues.append(WaypointIssue(
                    -1,
                    Severity.ERROR if margin < 10 else Severity.WARN,
                    f"battery margin {margin:.0f}% (consumption {consumed:.0f}%, available {available:.0f}%)",
                    category="battery",
                ))
        except Exception as e:
            report.warnings.append(f"battery budget skipped: {e}")
