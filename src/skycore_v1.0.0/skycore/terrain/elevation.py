"""Elevation data service"""

from typing import Dict, List, Optional

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class ElevationService(LoggerMixin):
    """Elevation data service using SRTM/DEM"""

import logging
