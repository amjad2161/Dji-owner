"""
SkyCore Notifications
Discord / Slack / Telegram webhooks for flight events
"""

import requests
from typing import Optional

class NotificationManager:
    def __init__(self, discord_webhook: Optional[str] = None, slack_webhook: Optional[str] = None):
        self.discord = discord_webhook
        self.slack = slack_webhook

    def send(self, message: str, level: str = "info"):
        print(f"📢 [{level.upper()}] {message}")
        # In real: send to webhooks
        if self.discord:
            requests.post(self.discord, json={"content": message})
        if self.slack:
            requests.post(self.slack, json={"text": message})
