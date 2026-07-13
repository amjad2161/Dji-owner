"""Pre-flight checklist orchestrator.

Aggregates checks from weather, airspace, geofence, battery, GPS, and
connectivity into a single report. Each check is independent and skipped
if its data source is unavailable, so partial checklists still complete.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Awaitable, Callable, Optional

from skycore.core.drone import Drone
from skycore.core.types import GeoPoint

log = logging.getLogger(__name__)


class ItemStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class ChecklistItem:
    name: str
    status: ItemStatus
    detail: str = ""
    data: Optional[dict] = None


@dataclass
class ChecklistReport:
    items: list[ChecklistItem] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def ok(self) -> bool:
        return all(i.status != ItemStatus.FAIL for i in self.items)

    @property
    def has_warnings(self) -> bool:
        return any(i.status == ItemStatus.WARN for i in self.items)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "ok": self.ok,
            "has_warnings": self.has_warnings,
            "items": [
                {"name": i.name, "status": i.status.value, "detail": i.detail, "data": i.data}
                for i in self.items
            ],
        }

    def render(self) -> str:
        glyphs = {
            ItemStatus.PASS: "✓",
            ItemStatus.WARN: "!",
            ItemStatus.FAIL: "✗",
            ItemStatus.SKIP: "-",
        }
        out = []
        for i in self.items:
            out.append(f"  {glyphs[i.status]} {i.name:<22} {i.detail}")
        verdict = "OK" if self.ok else "NOT SAFE"
        out.append("")
        out.append(f"  Result: {verdict}")
        return "\n".join(out)


class PreflightChecklist:
    """Compose any subset of preflight checks."""

    def __init__(
        self,
        drone: Optional[Drone] = None,
        home: Optional[GeoPoint] = None,
        max_wind_kph: float = 36.0,
        max_gust_kph: float = 50.0,
        min_battery_percent: float = 90.0,
        min_gps_satellites: int = 12,
    ):
        self.drone = drone
        self.home = home
        self.max_wind_kph = max_wind_kph
        self.max_gust_kph = max_gust_kph
        self.min_battery_percent = min_battery_percent
        self.min_gps_satellites = min_gps_satellites
        self._extras: list[Callable[[], Awaitable[ChecklistItem]]] = []

    def add_check(self, fn: Callable[[], Awaitable[ChecklistItem]]) -> None:
        """Register a custom async check. Should return a ChecklistItem."""
        self._extras.append(fn)

    async def run(self) -> ChecklistReport:
        report = ChecklistReport()

        report.items.append(await self._check_connectivity())

        if self.drone is not None:
            report.items.append(await self._check_telemetry())
            report.items.append(await self._check_battery())
            report.items.append(await self._check_gps())

        if self.home is not None:
            report.items.append(await self._check_weather())

        for fn in self._extras:
            try:
                report.items.append(await fn())
            except Exception as e:
                report.items.append(
                    ChecklistItem(name=fn.__name__, status=ItemStatus.WARN, detail=f"check raised: {e}")
                )

        return report

    async def _check_connectivity(self) -> ChecklistItem:
        if self.drone is None:
            return ChecklistItem("Connectivity", ItemStatus.SKIP, "no drone configured")
        if self.drone.is_connected:
            return ChecklistItem("Connectivity", ItemStatus.PASS, f"connected to {self.drone.name}")
        return ChecklistItem("Connectivity", ItemStatus.FAIL, "drone not connected")

    async def _check_telemetry(self) -> ChecklistItem:
        try:
            tm = await asyncio.wait_for(self.drone.get_telemetry(), timeout=3.0)
            return ChecklistItem(
                "Telemetry",
                ItemStatus.PASS,
                f"mode={tm.flight_mode.value}, signal={tm.signal_strength}%",
                data=tm.to_dict(),
            )
        except Exception as e:
            return ChecklistItem("Telemetry", ItemStatus.FAIL, f"no telemetry: {e}")

    async def _check_battery(self) -> ChecklistItem:
        try:
            tm = await self.drone.get_telemetry()
        except Exception as e:
            return ChecklistItem("Battery", ItemStatus.WARN, f"unknown: {e}")
        if tm.battery_percent < self.min_battery_percent:
            return ChecklistItem(
                "Battery",
                ItemStatus.WARN if tm.battery_percent > 50 else ItemStatus.FAIL,
                f"{tm.battery_percent:.0f}% (threshold {self.min_battery_percent:.0f}%)",
            )
        return ChecklistItem("Battery", ItemStatus.PASS, f"{tm.battery_percent:.0f}%")

    async def _check_gps(self) -> ChecklistItem:
        try:
            tm = await self.drone.get_telemetry()
        except Exception as e:
            return ChecklistItem("GPS", ItemStatus.WARN, f"unknown: {e}")
        if tm.gps_satellites < self.min_gps_satellites:
            return ChecklistItem(
                "GPS",
                ItemStatus.WARN if tm.gps_satellites >= 8 else ItemStatus.FAIL,
                f"{tm.gps_satellites} sats (need {self.min_gps_satellites}+)",
            )
        return ChecklistItem("GPS", ItemStatus.PASS, f"{tm.gps_satellites} sats")

    async def _check_weather(self) -> ChecklistItem:
        try:
            from skycore.weather import preflight_check
            loop = asyncio.get_running_loop()
            ok, issues, snap = await loop.run_in_executor(
                None, preflight_check, self.home.lat, self.home.lon, self.max_wind_kph, self.max_gust_kph
            )
            if ok:
                return ChecklistItem(
                    "Weather",
                    ItemStatus.PASS,
                    f"wind {snap.wind_speed_kph:.0f} kph, gust {snap.wind_gust_kph:.0f} kph, T={snap.temperature_c:.1f}°C",
                )
            return ChecklistItem("Weather", ItemStatus.FAIL, "; ".join(issues))
        except Exception as e:
            return ChecklistItem("Weather", ItemStatus.SKIP, f"weather lookup failed: {e}")
