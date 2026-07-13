"""Magnetometer and Compass Module"""

import math
from typing import Tuple, Optional, List
from dataclasses import dataclass
import threading

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


@dataclass
class HeadingData:
    """Heading information"""

import logging
