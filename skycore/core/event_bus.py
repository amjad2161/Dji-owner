"""Pub/sub event bus for telemetry and events.

Used to fan out one drone's telemetry stream to many consumers (web UI,
logger, recorder, mission monitor, vision pipeline, etc.) without each one
pulling its own stream from the drone.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

log = logging.getLogger(__name__)


class EventBus:
    """Simple in-process async pub/sub."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = {}

    async def publish(self, topic: str, message: Any) -> None:
        for q in list(self._subscribers.get(topic, set())):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                log.warning("Subscriber queue full for topic=%s; dropping", topic)

    def subscribe(self, topic: str, maxsize: int = 100) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers.setdefault(topic, set()).add(q)
        return q

    def unsubscribe(self, topic: str, q: asyncio.Queue) -> None:
        if topic in self._subscribers:
            self._subscribers[topic].discard(q)

    async def stream(self, topic: str) -> AsyncIterator[Any]:
        q = self.subscribe(topic)
        try:
            while True:
                yield await q.get()
        finally:
            self.unsubscribe(topic, q)


# Default global bus. Most code can use this.
default_bus = EventBus()
