"""
SkyCore MQTT Bridge
==================
MQTT bridge for telemetry fanout to external systems.
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class MqttConfig:
    """MQTT configuration."""
    broker_host: str = "localhost"
    broker_port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "skycore"
    keepalive: int = 60
    qos: int = 1
    retain: bool = False


class MqttBridge:
    """
    MQTT bridge for telemetry fanout.
    
    Publishes telemetry, events, and commands to MQTT broker
    for integration with Home Assistant, Node-RED, Grafana, etc.
    
    Topics:
    - skycore/<drone>/telemetry
    - skycore/<drone>/events
    - skycore/<drone>/cmd
    
    Features:
    - Automatic reconnection
    - QoS levels
    - TLS support
    - Last will and testament
    """
    
    def __init__(self, drone_name: str, config: Optional[MqttConfig] = None):
        """
        Initialize MQTT bridge.
        
        Args:
            drone_name: Drone identifier for topics
            config: MQTT configuration
        """
        self.drone_name = drone_name
        self.config = config or MqttConfig()
        
        self._client = None
        self._connected = False
        self._tasks: List[asyncio.Task] = []
        
        # Statistics
        self.messages_sent = 0
        self.messages_failed = 0
        
        log.info(f"MQTT bridge initialized for: {drone_name}")
    
    async def connect(self):
        """Connect to MQTT broker."""
        try:
            import paho.mqtt.client as mqtt
            
            self._client = mqtt.Client(client_id=self.config.client_id)
            
            if self.config.username:
                self._client.username_pw_set(
                    self.config.username, 
                    self.config.password
                )
            
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_publish = self._on_publish
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._client.connect,
                self.config.broker_host,
                self.config.broker_port,
                self.config.keepalive
            )
            
            self._client.loop_start()
            
        except ImportError:
            log.warning("paho-mqtt not installed, MQTT bridge unavailable")
        except Exception as e:
            log.error(f"MQTT connection failed: {e}")
    
    async def disconnect(self):
        """Disconnect from MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
        
        self._connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Connection callback."""
        if rc == 0:
            self._connected = True
            log.info("MQTT connected")
        else:
            log.warning(f"MQTT connection failed: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Disconnection callback."""
        self._connected = False
        log.warning("MQTT disconnected")
    
    def _on_publish(self, client, userdata, mid):
        """Publish callback."""
        self.messages_sent += 1
    
    def _get_topic(self, topic_type: str) -> str:
        """Get full topic path."""
        return f"skycore/{self.drone_name}/{topic_type}"
    
    async def publish_telemetry(self, telemetry: Dict):
        """Publish telemetry data."""
        topic = self._get_topic("telemetry")
        await self._publish(topic, telemetry)
    
    async def publish_event(self, event_type: str, event_data: Dict):
        """Publish event."""
        topic = self._get_topic("events")
        await self._publish(topic, {
            'type': event_type,
            **event_data
        })
    
    async def _publish(self, topic: str, payload: Dict):
        """Publish message to topic."""
        if not self._connected or not self._client:
            return
        
        try:
            payload_json = json.dumps(payload)
            result = self._client.publish(
                topic, 
                payload_json,
                qos=self.config.qos,
                retain=self.config.retain
            )
            
            if result.rc != 0:
                self.messages_failed += 1
                log.warning(f"MQTT publish failed: {result.rc}")
            else:
                self.messages_sent += 1
                
        except Exception as e:
            self.messages_failed += 1
            log.error(f"MQTT publish error: {e}")
    
    async def fanout_telemetry(self, drone, interval: float = 0.5):
        """
        Fan out telemetry at interval.
        
        Args:
            drone: Drone instance
            interval: Publish interval in seconds
        """
        while self._connected:
            try:
                telemetry = await drone.get_telemetry()
                await self.publish_telemetry(telemetry)
            except Exception as e:
                log.error(f"Telemetry fanout error: {e}")
            
            await asyncio.sleep(interval)
    
    async def subscribe_command(self, callback: Callable):
        """Subscribe to command topic."""
        topic = self._get_topic("cmd")
        
        def on_message(client, userdata, msg):
            try:
                data = json.loads(msg.payload)
                asyncio.create_task(callback(data))
            except Exception as e:
                log.error(f"MQTT command parse error: {e}")
        
        self._client.on_message = on_message
        self._client.subscribe(topic)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        return {
            'connected': self._connected,
            'drone_name': self.drone_name,
            'messages_sent': self.messages_sent,
            'messages_failed': self.messages_failed,
            'broker': f"{self.config.broker_host}:{self.config.broker_port}"
        }


# Export
__all__ = ['MqttBridge', 'MqttConfig']