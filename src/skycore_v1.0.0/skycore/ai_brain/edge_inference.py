"""Edge AI Inference - Local model execution"""

import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


@dataclass
class InferenceResult:
    """AI inference result"""

import logging
