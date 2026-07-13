"""
SkyCore Notifications Module
==========================
Multi-channel notification system.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Notification channels."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    DISCORD = "discord"
    SLACK = "slack"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


@dataclass
class Notification:
    """Notification message."""
    title: str
    body: str
    channel: NotificationChannel
    priority: NotificationPriority = NotificationPriority.NORMAL
    metadata: Dict = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3


class NotificationManager:
    """
    Multi-channel notification manager.
    
    Supports:
    - Email
    - SMS
    - Push notifications
    - Discord/Slack/Telegram
    - Webhooks
    """
    
    def __init__(self):
        self.handlers: Dict[NotificationChannel, Callable] = {}
        self.queue: List[Notification] = []
        self.sent_count = 0
        self.failed_count = 0
        log.info("Notification Manager initialized")
    
    def register_handler(self, channel: NotificationChannel, handler: Callable):
        """Register notification handler for channel."""
        self.handlers[channel] = handler
        log.info(f"Registered handler for {channel.value}")
    
    async def send(self, notification: Notification) -> bool:
        """Send notification."""
        channel = notification.channel
        
        if channel not in self.handlers:
            log.error(f"No handler for {channel.value}")
            return False
        
        try:
            handler = self.handlers[channel]
            if asyncio.iscoroutinefunction(handler):
                await handler(notification)
            else:
                handler(notification)
            
            self.sent_count += 1
            log.info(f"Notification sent: {notification.title}")
            return True
            
        except Exception as e:
            self.failed_count += 1
            log.error(f"Notification failed: {e}")
            
            if notification.retry_count < notification.max_retries:
                notification.retry_count += 1
                self.queue.append(notification)
            
            return False
    
    async def send_batch(self, notifications: List[Notification]) -> List[bool]:
        """Send multiple notifications."""
        results = []
        for notif in notifications:
            results.append(await self.send(notif))
        return results
    
    async def process_queue(self):
        """Process queued notifications."""
        while self.queue:
            notification = self.queue.pop(0)
            await self.send(notification)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get notification statistics."""
        return {
            'sent': self.sent_count,
            'failed': self.failed_count,
            'queued': len(self.queue),
            'channels': list(self.handlers.keys())
        }


# Export
__all__ = ['NotificationManager', 'Notification', 'NotificationChannel', 'NotificationPriority']