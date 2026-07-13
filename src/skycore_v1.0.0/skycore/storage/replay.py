"""Flight replay - replay recorded telemetry"""

from typing import List, Dict
from dataclasses import dataclass

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


@dataclass
class ReplayData:
    timestamp: float
    position: tuple
    velocity: tuple
    attitude: tuple


class FlightReplay(LoggerMixin):
    """Replay recorded flight data"""

import logging
