"""MQTT bridge for telemetry fan-out.

Publishes telemetry to an MQTT broker so any number of subscribers (Home
Assistant, Node-RED, Grafana, custom dashboards, fleet management) can
consume it without going through SkyCore's WebSocket.

Default topics:
    skycore/<drone>/telemetry      JSON telemetry frames
    skycore/<drone>/events         lifecycle events
    skycore/<drone>/cmd            inbound commands (subscribed)
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Optional

from skycore.core.drone import Drone
from skycore.core.event_bus import EventBus

log = logging.getLogger(__name__)


@dataclass
class MqttBridge:
    drone_name: str
    broker_host: str = "localhost"
    broker_port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    qos: int = 0
    base_topic: str = "skycore"

    def __post_init__(self) -> None:
        self._client = None
        self._connected = False

    def _topic(self, suffix: str) -> str:
        return f"{self.base_topic}/{self.drone_name}/{suffix}"

    async def connect(self) -> None:
        try:
            from paho.mqtt import client as mqtt
        except ImportError as e:
            raise ImportError("paho-mqtt is required. pip install paho-mqtt") from e
        c = mqtt.Client(client_id=f"skycore-{self.drone_name}", protocol=mqtt.MQTTv5)
        if self.username:
            c.username_pw_set(self.username, self.password)
        c.on_connect = lambda *args, **kw: log.info("MQTT connected to %s:%d", self.broker_host, self.broker_port)
        c.connect(self.broker_host, self.broker_port, keepalive=60)
        c.loop_start()
        self._client = c
        self._connected = True

    async def disconnect(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        self._connected = False

    def publish(self, suffix: str, payload: dict) -> None:
        if not self._connected:
            return
        self._client.publish(self._topic(suffix), json.dumps(payload), qos=self.qos)

    async def fanout_telemetry(self, drone: Drone) -> None:
        """Stream drone telemetry to MQTT until cancelled."""
        try:
            async for tm in drone.telemetry_stream():
                self.publish("telemetry", tm.to_dict())
        except asyncio.CancelledError:
            return

    async def fanout_bus(self, bus: EventBus, topic: str = "telemetry", suffix: str = "telemetry") -> None:
        """Stream from a generic EventBus topic to MQTT."""
        async for msg in bus.stream(topic):
            self.publish(suffix, msg if isinstance(msg, dict) else {"data": msg})
