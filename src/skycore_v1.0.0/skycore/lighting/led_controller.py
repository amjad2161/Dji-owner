"""LED Controller for lighting effects"""

import time
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import threading

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class LEDPattern(Enum):
    """LED pattern types"""

import logging
