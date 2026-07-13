"""Geotagging photos with GPS coordinates"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
import struct
import os

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


@dataclass
class GeoTagInfo:
    """Geotag metadata"""

import logging
