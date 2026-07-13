"""
SkyCore Core - Event Bus
Simple async event system for pub/sub communication
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine, Dict, List, Optional

log = logging.getLogger(__name__)


class EventBus:
    """Simple async pub/sub event bus for inter-component communication."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
    
    def subscribe(self, event: str) -> asyncio.Queue:
        """Subscribe to an event, returns queue to receive messages."""
        q = asyncio.Queue()
        self._subscribers[event].append(q)
        return q
    
    def unsubscribe(self, event: str, q: asyncio.Queue) -> None:
        """Unsubscribe a queue from an event."""
        if event in self._subscribers and q in self._subscribers[event]:
            self._subscribers[event].remove(q)
    
    async def publish(self, event: str, message: Any) -> None:
        """Publish a message to all subscribers of an event."""
        for q in self._subscribers.get(event, []):
            try:
                await asyncio.wait_for(q.put(message), timeout=1.0)
            except asyncio.TimeoutError:
                log.warning("Subscriber queue full, dropping message")
    
    def on(self, event: str, handler: Callable[..., Coroutine]) -> None:
        """Register an async handler for an event."""
        self._handlers[event].append(handler)
    
    async def emit(self, event: str, *args, **kwargs) -> None:
        """Emit an event, calling all registered handlers."""
        for handler in self._handlers.get(event, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args, **kwargs)
                else:
                    handler(*args, **kwargs)
            except Exception as e:
                log.error(f"Handler error for {event}: {e}")


# Global instance
_default_bus = EventBus()


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return _default_bus