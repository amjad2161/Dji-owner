"""Mission scheduler with sun-position awareness.

Schedule async functions to run at specific UTC times, with helpers for
computing golden-hour windows for a location (uses `astral`).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional

log = logging.getLogger(__name__)


@dataclass
class ScheduledMission:
    name: str
    when: datetime  # UTC
    fn: Callable[[], Awaitable[None]]


def golden_hour_at(lat: float, lon: float, when: Optional[datetime] = None) -> tuple[datetime, datetime, datetime, datetime]:
    """Compute golden-hour windows for a date.

    Returns (morning_start, morning_end, evening_start, evening_end) in UTC.
    Morning: from sunrise to sunrise+1h. Evening: sunset-1h to sunset.
    """
    try:
        from astral import LocationInfo
        from astral.sun import sun
    except ImportError as e:
        raise ImportError("astral is required. pip install astral") from e
    when = when or datetime.now(timezone.utc)
    loc = LocationInfo(latitude=lat, longitude=lon)
    s = sun(loc.observer, date=when.date(), tzinfo=timezone.utc)
    return (
        s["sunrise"],
        s["sunrise"] + timedelta(hours=1),
        s["sunset"] - timedelta(hours=1),
        s["sunset"],
    )


class Scheduler:
    """In-process mission scheduler. Wakes up to run pending missions."""

    def __init__(self) -> None:
        self._missions: list[ScheduledMission] = []
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def add(self, mission: ScheduledMission) -> None:
        self._missions.append(mission)
        self._missions.sort(key=lambda m: m.when)

    def list(self) -> list[ScheduledMission]:
        return list(self._missions)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    async def _loop(self) -> None:
        try:
            while self._running:
                if self._missions:
                    nxt = self._missions[0]
                    delay = (nxt.when - datetime.now(timezone.utc)).total_seconds()
                    if delay <= 0:
                        self._missions.pop(0)
                        try:
                            log.info("Running scheduled mission: %s", nxt.name)
                            await nxt.fn()
                        except Exception as e:
                            log.error("Mission %s failed: %s", nxt.name, e)
                    else:
                        await asyncio.sleep(min(delay, 30.0))
                else:
                    await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            return
