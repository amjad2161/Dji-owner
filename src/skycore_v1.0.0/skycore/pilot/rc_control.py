"""RC Controller for manual pilot input"""

import time
from typing import Dict, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class RCState(Enum):
    """RC receiver state"""

import logging
