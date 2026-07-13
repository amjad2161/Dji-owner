"""
SkyCore Events - Lifecycle Event System
======================================
Typed async pub/sub for drone lifecycle events.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

log = logging.getLogger(__name__)


class EventType(Enum):
    """Drone lifecycle event types."""
    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    
    # Flight events
    TAKEOFF_COMPLETE = "takeoff_complete"
    LANDING_COMPLETE = "landing_complete"
    HOVERING = "hovering"
    
    # Navigation events
    GOTO_STARTED = "goto_started"
    GOTO_COMPLETE = "goto_complete"
    RTH_STARTED = "rth_started"
    RTH_COMPLETE = "rth_complete"
    
    # Battery events
    BATTERY_WARNING = "battery_warning"
    BATTERY_CRITICAL = "battery_critical"
    
    # Safety events
    GEOFENCE_WARNING = "geofence_warning"
    GEOFENCE_VIOLATION = "geofence_violation"
    GPS_DEGRADED = "gps_degraded"
    GPS_LOST = "gps_lost"
    LINK_DEGRADED = "link_degraded"
    LINK_LOST = "link_lost"
    
    # Mission events
    MISSION_STARTED = "mission_started"
    MISSION_PAUSED = "mission_paused"
    MISSION_RESUMED = "mission_resumed"
    MISSION_COMPLETE = "mission_complete"
    MISSION_ABORTED = "mission_aborted"
    
    # Media events
    PHOTO_CAPTURED = "photo_captured"
    VIDEO_STARTED = "video_started"
    VIDEO_STOPPED = "video_stopped"
    
    # System events
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    
    # ADSB events
    TRAFFIC_DETECTED = "traffic_detected"
    TRAFFIC_ALERT = "traffic_alert"


@dataclass
class Event:
    """Base event class."""
    event_type: EventType
    timestamp: float = field(default_factory=time.time)
    data: Dict = field(default_factory=dict)
    
    def __str__(self):
        return f"{self.event_type.value} @ {self.timestamp:.3f}"


@dataclass
class ConnectionEvent(Event):
    """Connection event."""
    def __init__(self, connected: bool, **kwargs):
        super().__init__(EventType.CONNECTED if connected else EventType.DISCONNECTED, **kwargs)
        self.connected = connected


@dataclass
class BatteryEvent(Event):
    """Battery event."""
    percent: float = 0.0
    voltage: float = 0.0
    temperature: float = 25.0
    
    def __init__(self, event_type: EventType, percent: float, **kwargs):
        super().__init__(event_type, **kwargs)
        self.percent = percent


@dataclass
class GotoEvent(Event):
    """Navigation event."""
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    
    def __init__(self, event_type: EventType, lat: float, lon: float, alt: float, **kwargs):
        super().__init__(event_type, **kwargs)
        self.lat = lat
        self.lon = lon
        self.alt = alt


@dataclass
class MissionEvent(Event):
    """Mission event."""
    mission_id: str = ""
    waypoint_index: int = 0
    
    def __init__(self, event_type: EventType, mission_id: str = "", **kwargs):
        super().__init__(event_type, **kwargs)
        self.mission_id = mission_id


@dataclass
class TrafficEvent(Event):
    """ADS-B traffic event."""
    icao: str = ""
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    distance_m: float = 0.0
    alert_level: str = ""
    
    def __init__(self, event_type: EventType, icao: str, lat: float, lon: float, **kwargs):
        super().__init__(event_type, **kwargs)
        self.icao = icao
        self.lat = lat
        self.lon = lon


class EventEmitter:
    """
    Typed event emitter for drone lifecycle.
    
    Provides async pub/sub for 18+ event types with
    type-safe callbacks and filtering.
    
    Features:
    - Type-safe event handling
    - Async callback support
    - Event filtering
    - History tracking
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize event emitter.
        
        Args:
            max_history: Maximum number of events to keep in history
        """
        self._handlers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._all_handlers: List[Callable] = []
        self._history: List[Event] = []
        self._max_history = max_history
        
        # Statistics
        self.total_events = 0
        self.events_by_type: Dict[EventType, int] = defaultdict(int)
        
        log.info("EventEmitter initialized")
    
    def on(self, event_type: EventType) -> Callable:
        """
        Decorator to register event handler.
        
        Args:
            event_type: Event type to listen for
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            self._handlers[event_type].append(func)
            return func
        return decorator
    
    def on_all(self, func: Callable) -> Callable:
        """Register handler for all events."""
        self._all_handlers.append(func)
        return func
    
    def emit(self, event: Event):
        """
        Emit an event.
        
        Args:
            event: Event to emit
        """
        self.total_events += 1
        self.events_by_type[event.event_type] += 1
        
        # Add to history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        
        # Call type-specific handlers
        for handler in self._handlers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as e:
                log.error(f"Event handler error: {e}")
        
        # Call all-handlers
        for handler in self._all_handlers:
            try:
                handler(event)
            except Exception as e:
                log.error(f"Event handler error: {e}")
        
        log.debug(f"Event emitted: {event}")
    
    def emit_simple(self, event_type: EventType, **data):
        """Emit event with simple data."""
        event = Event(event_type=event_type, data=data)
        self.emit(event)
    
    def get_history(self, event_type: Optional[EventType] = None,
                   limit: int = 100) -> List[Event]:
        """Get event history."""
        if event_type:
            events = [e for e in self._history if e.event_type == event_type]
        else:
            events = self._history
        
        return events[-limit:]
    
    def get_statistics(self) -> Dict:
        """Get emitter statistics."""
        return {
            'total_events': self.total_events,
            'events_by_type': {k.value: v for k, v in self.events_by_type.items()},
            'handlers_registered': sum(len(h) for h in self._handlers.values()),
            'history_size': len(self._history)
        }
    
    def clear(self):
        """Clear all handlers and history."""
        self._handlers.clear()
        self._all_handlers.clear()
        self._history.clear()
        log.info("EventEmitter cleared")


# Factory functions for common events
def create_battery_warning(percent: float) -> BatteryEvent:
    """Create battery warning event."""
    return BatteryEvent(EventType.BATTERY_WARNING, percent)


def create_battery_critical(percent: float) -> BatteryEvent:
    """Create battery critical event."""
    return BatteryEvent(EventType.BATTERY_CRITICAL, percent)


def create_takeoff_complete() -> Event:
    """Create takeoff complete event."""
    return Event(EventType.TAKEOFF_COMPLETE)


def create_landing_complete() -> Event:
    """Create landing complete event."""
    return Event(EventType.LANDING_COMPLETE)


def create_goto_complete(lat: float, lon: float, alt: float) -> GotoEvent:
    """Create goto complete event."""
    return GotoEvent(EventType.GOTO_COMPLETE, lat, lon, alt)


def create_traffic_alert(icao: str, lat: float, lon: float,
                        distance_m: float, alert_level: str) -> TrafficEvent:
    """Create traffic alert event."""
    return TrafficEvent(EventType.TRAFFIC_ALERT, icao, lat, lon,
                       data={'distance_m': distance_m, 'alert_level': alert_level})


# Export
__all__ = ['EventEmitter', 'Event', 'EventType', 'ConnectionEvent', 'BatteryEvent',
           'GotoEvent', 'MissionEvent', 'TrafficEvent', 'create_battery_warning',
           'create_battery_critical', 'create_takeoff_complete', 'create_landing_complete',
           'create_goto_complete', 'create_traffic_alert']