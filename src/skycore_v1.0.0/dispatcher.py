"""Notification dispatch for events.

Fire-and-forget webhooks for Discord, Slack, Telegram, or any custom HTTP
endpoint. Wire into mission lifecycle (start, complete, abort) or safety
guards (battery low, geofence breach, link loss).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class NotificationDispatcher:
    discord_webhook: Optional[str] = None
    slack_webhook: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    custom_webhook: Optional[str] = None

    async def send(self, title: str, message: str, level: str = "info") -> None:
        try:
            import aiohttp
        except ImportError:
            log.warning("aiohttp not installed; cannot send notifications")
            return
        async with aiohttp.ClientSession() as session:
            if self.discord_webhook:
                await self._discord(session, title, message, level)
            if self.slack_webhook:
                await self._slack(session, title, message, level)
            if self.telegram_bot_token and self.telegram_chat_id:
                await self._telegram(session, title, message)
            if self.custom_webhook:
                await self._custom(session, title, message, level)

    async def _discord(self, session, title, message, level):
        color = {"info": 0x3498DB, "warn": 0xF1C40F, "error": 0xE74C3C}.get(level, 0x95A5A6)
        try:
            await session.post(
                self.discord_webhook,
                json={"embeds": [{"title": title, "description": message, "color": color}]},
            )
        except Exception as e:
            log.warning("Discord webhook failed: %s", e)

    async def _slack(self, session, title, message, level):
        try:
            await session.post(self.slack_webhook, json={"text": f"*{title}*\n{message}"})
        except Exception as e:
            log.warning("Slack webhook failed: %s", e)

    async def _telegram(self, session, title, message):
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        try:
            await session.post(
                url,
                json={
                    "chat_id": self.telegram_chat_id,
                    "text": f"*{title}*\n{message}",
                    "parse_mode": "Markdown",
                },
            )
        except Exception as e:
            log.warning("Telegram webhook failed: %s", e)

    async def _custom(self, session, title, message, level):
        try:
            await session.post(
                self.custom_webhook,
                json={"title": title, "message": message, "level": level},
            )
        except Exception as e:
            log.warning("Custom webhook failed: %s", e)
