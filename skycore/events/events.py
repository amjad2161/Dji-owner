"""Drone lifecycle events.

A typed event system on top of the EventBus. Subscribe to the events you
care about; emit from missions, safety guards, or custom flows.

Use it to wire up logging, persistence, notifications, dashboards, etc.
without coupling them to mission code.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Type, TypeVar

log = logging.getLogger(__name__)


@dataclass
class DroneEvent:
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    drone_name: str = ""


@dataclass
class ConnectionOpened(DroneEvent): pass


@dataclass
class ConnectionClosed(DroneEvent): pass


@dataclass
class TakeoffStarted(DroneEvent):
    altitude_m: float = 0.0


@dataclass
class TakeoffComplete(DroneEvent):
    altitude_m: float = 0.0


@dataclass
class LandingStarted(DroneEvent): pass


@dataclass
class LandingComplete(DroneEvent): pass


@dataclass
class GotoStarted(DroneEvent):
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0


@dataclass
class GotoComplete(DroneEvent):
    lat: float = 0.0
    lon: float = 0.0


@dataclass
class RTHTriggered(DroneEvent):
    reason: str = ""


@dataclass
class BatteryWarning(DroneEvent):
    percent: float = 0.0
    threshold: float = 0.0


@dataclass
class GeofenceWarning(DroneEvent):
    detail: str = ""


@dataclass
class MissionStarted(DroneEvent):
    name: str = ""
    waypoint_count: int = 0


@dataclass
class MissionComplete(DroneEvent):
    name: str = ""


@dataclass
class MissionAborted(DroneEvent):
    name: str = ""
    reason: str = ""


@dataclass
class PhotoTaken(DroneEvent):
    uri: str = ""


@dataclass
class RecordStarted(DroneEvent): pass


@dataclass
class RecordStopped(DroneEvent): pass


E = TypeVar("E", bound=DroneEvent)
Handler = Callable[[DroneEvent], Awaitable[None]]


class EventEmitter:
    """Type-keyed async event bus."""

    def __init__(self) -> None:
        self._handlers: dict[Type[DroneEvent], list[Handler]] = {}

    def on(self, event_type: Type[E], handler: Handler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def off(self, event_type: Type[E], handler: Handler) -> None:
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    async def emit(self, event: DroneEvent) -> None:
        for et, handlers in self._handlers.items():
            if isinstance(event, et):
                for h in list(handlers):
                    try:
                        await h(event)
                    except Exception as e:
                        log.warning("event handler %r failed: %s", h, e)


# Default global emitter
default_emitter = EventEmitter()
