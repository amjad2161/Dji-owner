"""ODM Manager for photogrammetry processing"""

from enum import Enum
from typing import List, Optional, Dict

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class ProcessingStatus(Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'


class ODMProject:
    name: str
    images_path: str
    output_path: str
    status: ProcessingStatus
    progress: float
    orthophoto_path: Optional[str]
    dem_path: Optional[str]
    report_path: Optional[str]


class ODMManager(LoggerMixin):
    """Manages ODM photogrammetry processing"""

import logging
