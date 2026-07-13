"""GNSS Receiver - Multi-constellation support"""

import math
from typing import Dict, List, Tuple, Optional
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


class GNSSConstellation(Enum):
    GPS = 'GPS'
    GLONASS = 'GLONASS'
    GALILEO = 'Galileo'
    BEIDOU = 'BeiDou'
    QZSS = 'QZSS'
    SBAS = 'SBAS'


@dataclass
class SVMeasurement:
    """Satellite Vehicle measurement"""

import logging
