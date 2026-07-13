"""Flight time estimation based on current conditions"""

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class FlightTimeEstimator(LoggerMixin):
    """Estimates flight time based on conditions"""

import logging
