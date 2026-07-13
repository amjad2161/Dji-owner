"""
SkyCore Professional Logging (inspired by high-quality projects like PX4 + structlog)
"""

import logging
import structlog
from datetime import datetime

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("skycore")

def log_security_event(event_type: str, details: dict, severity: str = "info"):
    """Professional security event logging"""
    log_func = getattr(logger, severity)
    log_func(
        event_type=event_type,
        timestamp=datetime.utcnow().isoformat(),
        details=details,
        system="SkyCore Security v5.5"
    )
