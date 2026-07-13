"""Telemetry logger - flight data recording"""

import time
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class LogLevel(Enum):
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


@dataclass
class LogEntry:
    timestamp: float
    level: str
    source: str
    message: str
    data: Optional[Dict] = None


class TelemetryLogger(LoggerMixin):
    """Logs telemetry data and system events"""

import logging
