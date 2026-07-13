"""Stick mapping for different transmitter modes"""

from typing import Dict, Tuple
from enum import Enum

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class TransmitterMode(Enum):
    """Transmitter mode (stick layout)"""

import logging
