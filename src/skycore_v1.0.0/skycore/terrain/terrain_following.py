"""Terrain following for safe low-altitude flight"""

import math
from typing import Tuple, Optional

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class TerrainData:
    elevation: float = 0
    slope: float = 0
    safe_altitude: float = 10


class TerrainFollower(LoggerMixin):
    """Terrain following for low-altitude flight"""

import logging
