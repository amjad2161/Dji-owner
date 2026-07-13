"""Flip Manager - Pre-programmed aerial maneuvers"""

import time
import math
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from enum import Enum

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class FlipType(Enum):
    """Flip/roll types"""

import logging
