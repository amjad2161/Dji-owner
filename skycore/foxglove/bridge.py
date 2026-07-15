"""Foxglove WebSocket bridge for advanced telemetry visualization.

Foxglove (https://foxglove.dev) is a powerful telemetry visualizer used by
the robotics industry. It can render 3D paths, time-series, custom panels,
and replay flights. SkyCore exposes a Foxglove WebSocket server so you
can connect Foxglove Studio (free desktop app) directly to a flight.

The bridge implements a minimal Foxglove WebSocket protocol with one
channel: `/skycore/telemetry` carrying JSON-serialized telemetry frames.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from skycore.core.event_bus import EventBus

log = logging.getLogger(__name__)


class FoxgloveServer:
    """Minimal Foxglove WebSocket protocol server.

    Compatible with Foxglove Studio's WebSocket data source.
    See https://github.com/foxglove/ws-protocol for the spec.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765, channel_topic: str = "/skycore/telemetry"):
        self.host = host
        self.port = port
        self.channel_topic = channel_topic
        self._server = None
        self._clients: set = set()
        self._channel_id = 1

    async def start(self) -> None:
        try:
            import websockets
        except ImportError as e:
            raise ImportError("websockets is required. pip install websockets") from e

        async def handler(ws):
            self._clients.add(ws)
            try:
                # Server info per Foxglove WS protocol
                await ws.send(json.dumps({
                    "op": "serverInfo",
                    "name": "skycore",
                    "capabilities": [],
                    "supportedEncodings": ["json"],
                    "metadata": {},
                }))
                # Advertise one channel
                await ws.send(json.dumps({
                    "op": "advertise",
                    "channels": [{
                        "id": self._channel_id,
                        "topic": self.channel_topic,
                        "encoding": "json",
                        "schemaName": "skycore.Telemetry",
                        "schema": json.dumps({
                            "type": "object",
                            "properties": {
                                "timestamp": {"type": "string"},
                                "position": {"type": "object"},
                                "battery": {"type": "object"},
                                "yaw": {"type": "number"},
                                "mode": {"type": "string"},
                            },
                        }),
                        "schemaEncoding": "jsonschema",
                    }],
                }))
                async for _ in ws:
                    pass  # ignore client subscribe; we broadcast everything
            finally:
                self._clients.discard(ws)

        self._server = await websockets.serve(
            handler, self.host, self.port,
            subprotocols=["foxglove.websocket.v1"],
        )
        log.info("Foxglove WS server listening on ws://%s:%d", self.host, self.port)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def broadcast(self, telemetry: dict) -> None:
        if not self._clients:
            return
        # Foxglove message frame: {op: "messageData", channelId, timestamp_ns, data}
        ts_ns = 0
        try:
            from datetime import datetime, timezone
            ts_ns = int(datetime.now(timezone.utc).timestamp() * 1e9)
        except Exception:
            pass
        msg = json.dumps({
            "op": "messageData",
            "channelId": self._channel_id,
            "receiveTime": ts_ns,
            "data": telemetry,
        })
        dead = []
        for ws in self._clients:
            try:
                await ws.send(msg)
            except Exception:
                dead.append(ws)
        for d in dead:
            self._clients.discard(d)

    async def fanout_bus(self, bus: EventBus, topic: str = "telemetry") -> None:
        async for msg in bus.stream(topic):
            await self.broadcast(msg if isinstance(msg, dict) else {"data": msg})
