"""Navigation Lights - FAA/ICAO compliant"""

from enum import Enum
from typing import Tuple

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class NavLightColor(Enum):
    WHITE = 'white'
    RED = 'red'      # Port
    GREEN = 'green'  # Starboard
    YELLOW = 'yellow'  # Anti-collision
    BLUE = 'blue'    # Special operations


class NavLightState(Enum):
    OFF = 'off'
    ON = 'on'
    FLASHING = 'flashing'
    STROBE = 'strobe'


class NavigationLights(LoggerMixin):
    """

import logging
