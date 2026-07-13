"""IMU Sensor - Gyroscope and Accelerometer"""

import math
import time
from typing import Tuple, Optional
from dataclasses import dataclass
import threading

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


@dataclass
class IMUData:
    """IMU measurement data"""

import logging
