"""Flight profile management"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class ProfileType(Enum):
    """Flight profile types"""

import logging
