"""
SkyCore Communications Module
============================
Communication protocols and message handling.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger(__name__)


class Protocol(Enum):
    """Communication protocols."""
    MAVLINK = "mavlink"
    LORA = "lora"
    WIFI = "wifi"
    CELLULAR = "cellular"
    SATELLITE = "satellite"


@dataclass
class LinkStatus:
    """Communication link status."""
    protocol: Protocol
    connected: bool
    signal_strength: float = -100.0  # dBm
    latency_ms: float = 0.0
    packet_loss: float = 0.0  # percentage
    bandwidth_kbps: float = 0.0
    last_heartbeat: float = 0.0


class CommManager:
    """
    Communication manager for multi-link operations.
    
    Manages multiple communication links with automatic failover.
    """
    
    def __init__(self):
        self.links: Dict[Protocol, LinkStatus] = {}
        self.primary_link: Optional[Protocol] = None
        self._running = False
    
    async def add_link(self, protocol: Protocol, config: Dict):
        """Add communication link."""
        self.links[protocol] = LinkStatus(protocol=protocol, connected=False)
        log.info(f"Added {protocol.value} link")
    
    async def connect(self, protocol: Protocol) -> bool:
        """Connect to specific link."""
        if protocol in self.links:
            self.links[protocol].connected = True
            self.links[protocol].last_heartbeat = asyncio.get_event_loop().time()
            log.info(f"Connected to {protocol.value}")
            return True
        return False
    
    async def send(self, data: bytes, priority: int = 0) -> bool:
        """Send data over primary link."""
        if self.primary_link and self.primary_link in self.links:
            link = self.links[self.primary_link]
            if link.connected:
                # Send implementation
                return True
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get all link statuses."""
        return {
            protocol.value: {
                'connected': link.connected,
                'signal': link.signal_strength,
                'latency': link.latency_ms
            }
            for protocol, link in self.links.items()
        }


__all__ = ['CommManager', 'Protocol', 'LinkStatus']