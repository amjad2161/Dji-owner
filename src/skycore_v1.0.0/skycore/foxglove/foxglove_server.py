"""
SkyCore Foxglove Bridge
=======================
WebSocket bridge for Foxglove Studio visualization.
"""

import asyncio
import logging
import json
import struct
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger(__name__)


class MessageSchema(Enum):
    """Foxglove message schemas."""
    PROTOBUF = "protobuf"
    JSON = "json"
    flatbuffers = "flatbuffers"


@dataclass
class FoxgloveConfig:
    """Foxglove bridge configuration."""
    port: int = 8765
    host: str = "0.0.0.0"
    topic_prefix: str = "skycore"


class FoxgloveServer:
    """
    Foxglove WebSocket server for telemetry visualization.
    
    Exposes live telemetry to Foxglove Studio for:
    - 3D visualization
    - Time-series charts
    - Message inspection
    - Replay
    
    Features:
    - Foxglove WebSocket protocol
    - Multiple topic support
    - Binary message encoding
    """
    
    def __init__(self, config: Optional[FoxgloveConfig] = None):
        """
        Initialize Foxglove server.
        
        Args:
            config: Server configuration
        """
        self.config = config or FoxgloveConfig()
        
        self._server = None
        self._clients: List[asyncio.WebSocketServerProtocol] = []
        self._running = False
        
        # Statistics
        self.messages_sent = 0
        self.clients_connected = 0
        
        log.info(f"Foxglove server initialized: {self.config.host}:{self.config.port}")
    
    async def start(self):
        """Start Foxglove WebSocket server."""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.config.host,
            self.config.port
        )
        
        self._running = True
        log.info(f"Foxglove server started on port {self.config.port}")
    
    async def stop(self):
        """Stop Foxglove server."""
        self._running = False
        
        for client in self._clients:
            await client.close()
        
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        log.info("Foxglove server stopped")
    
    async def _handle_client(self, client: asyncio.WebSocketServerProtocol, path: str):
        """Handle new WebSocket client."""
        self._clients.append(client)
        self.clients_connected += 1
        log.info(f"Foxglove client connected: {len(self._clients)} clients")
        
        # Send channel info
        await self._send_channel_info(client)
        
        try:
            async for message in client:
                # Handle client messages (mostly subscriptions)
                await self._handle_message(client, message)
        except Exception as e:
            log.debug(f"Foxglove client error: {e}")
        finally:
            self._clients.remove(client)
            log.info(f"Foxglove client disconnected: {len(self._clients)} clients")
    
    async def _send_channel_info(self, client):
        """Send Foxglove channel configuration."""
        channels = [
            {
                'id': 1,
                'topic': f"{self.config.topic_prefix}/telemetry",
                'schemaName': 'skycore/Telemetry',
                'schema': json.dumps({
                    'type': 'object',
                    'properties': {
                        'timestamp': {'type': 'number'},
                        'position': {
                            'type': 'object',
                            'properties': {
                                'lat': {'type': 'number'},
                                'lon': {'type': 'number'},
                                'alt': {'type': 'number'}
                            }
                        },
                        'velocity': {'type': 'object'},
                        'attitude': {'type': 'object'},
                        'battery': {'type': 'object'}
                    }
                })
            },
            {
                'id': 2,
                'topic': f"{self.config.topic_prefix}/gps",
                'schemaName': 'sensor_msgs/GpsFix',
                'schema': json.dumps({
                    'type': 'object',
                    'properties': {
                        'latitude': {'type': 'number'},
                        'longitude': {'type': 'number'},
                        'altitude': {'type': 'number'}
                    }
                })
            }
        ]
        
        # Foxglove connection message
        msg = json.dumps({
            'type': 'connection',
            'data': {
                'channelId': 1,
                'op': 'subscribe',
                'subscriptions': [{'channelId': 1, 'subscriptionId': 1}]
            }
        })
        
        await client.send(msg)
    
    async def _handle_message(self, client, message):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            # Handle subscription requests
            if data.get('type') == 'subscribe':
                # Acknowledge subscription
                log.debug(f"Subscription request: {data}")
                
        except json.JSONDecodeError:
            pass
    
    async def publish_telemetry(self, telemetry: Dict):
        """
        Publish telemetry to all connected clients.
        
        Args:
            telemetry: Telemetry dictionary
        """
        if not self._clients:
            return
        
        # Foxglove message format
        foxglove_msg = {
            'type': 'message',
            'data': {
                'channelId': 1,
                'timestamp': int(telemetry.get('timestamp', 0) * 1e9),  # nanoseconds
                'schemaName': 'skycore/Telemetry',
                'message': json.dumps(telemetry).encode('utf-8')
            }
        }
        
        msg_bytes = json.dumps(foxglove_msg).encode('utf-8')
        
        for client in self._clients:
            try:
                await client.send(msg_bytes)
                self.messages_sent += 1
            except Exception as e:
                log.error(f"Foxglove publish error: {e}")
    
    async def publish_gps(self, lat: float, lon: float, alt: float, timestamp: float):
        """Publish GPS data."""
        gps_data = {
            'latitude': lat,
            'longitude': lon,
            'altitude': alt,
            'timestamp': timestamp
        }
        
        foxglove_msg = {
            'type': 'message',
            'data': {
                'channelId': 2,
                'timestamp': int(timestamp * 1e9),
                'schemaName': 'sensor_msgs/GpsFix',
                'message': json.dumps(gps_data).encode('utf-8')
            }
        }
        
        msg_bytes = json.dumps(foxglove_msg).encode('utf-8')
        
        for client in self._clients:
            try:
                await client.send(msg_bytes)
                self.messages_sent += 1
            except Exception as e:
                log.error(f"GPS publish error: {e}")
    
    async def fanout_bus(self, bus, topic: str = "telemetry"):
        """
        Fan out EventBus messages to Foxglove.
        
        Args:
            bus: EventBus instance
            topic: Topic name
        """
        async def handler(event):
            await self.publish_telemetry(event.data)
        
        bus.on_all(handler)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get server statistics."""
        return {
            'running': self._running,
            'port': self.config.port,
            'clients': len(self._clients),
            'messages_sent': self.messages_sent
        }


# Export
__all__ = ['FoxgloveServer', 'FoxgloveConfig', 'MessageSchema']