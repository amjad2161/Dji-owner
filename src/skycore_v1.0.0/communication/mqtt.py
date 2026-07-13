"""MQTT telemetry broker for drone communication.

Implements:
- MQTT client for telemetry streaming
- Topic management
- Message queuing
- QoS levels
- TLS/SSL support
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable
import time
import json
import struct


@dataclass
class MQTTConfig:
    """MQTT configuration."""
    broker: str = "localhost"
    port: int = 1883
    
    # Authentication
    username: Optional[str] = None
    password: Optional[str] = None
    
    # TLS
    use_tls: bool = False
    tls_cert: Optional[str] = None
    
    # Topics
    base_topic: str = "skycore"
    
    # QoS
    default_qos: int = 0  # 0=at most once, 1=at least once, 2=exactly once
    
    # Keepalive
    keepalive: int = 60  # seconds
    
    # Message size
    max_message_size: int = 256 * 1024  # 256KB


class TelemetryTopic:
    """Telemetry topic structure."""
    
    # Topic templates
    TELEMETRY = "{base}/telemetry/{drone_id}"
    STATUS = "{base}/status/{drone_id}"
    COMMAND = "{base}/command/{drone_id}"
    GPS = "{base}/gps/{drone_id}"
    IMU = "{base}/imu/{drone_id}"
    BATTERY = "{base}/battery/{drone_id}"
    ATTITUDE = "{base}/attitude/{drone_id}"
    HOME = "{base}/home/{drone_id}"
    ALERTS = "{base}/alerts"
    GCS_COMMAND = "{base}/gcs/{drone_id}/command"
    
    def __init__(self, base_topic: str, drone_id: str = "drone001"):
        self.base_topic = base_topic
        self.drone_id = drone_id
    
    def get(self, topic_type: str) -> str:
        """Get full topic path."""
        template = getattr(self, topic_type.upper(), self.TELEMETRY)
        return template.format(base=self.base_topic, drone_id=self.drone_id)
    
    def get_telemetry(self) -> str:
        return self.get("TELEMETRY")
    
    def get_status(self) -> str:
        return self.get("STATUS")
    
    def get_gps(self) -> str:
        return self.get("GPS")
    
    def get_command(self) -> str:
        return self.get("COMMAND")
    
    def get_alerts(self) -> str:
        return self.get("ALERTS")


@dataclass
class TelemetryMessage:
    """Telemetry message with timestamp."""
    timestamp: float
    topic: str
    payload: bytes
    qos: int = 0
    retained: bool = False
    
    @staticmethod
    def from_dict(topic: str, data: Dict, qos: int = 0) -> 'TelemetryMessage':
        """Create from dictionary."""
        return TelemetryMessage(
            timestamp=time.time(),
            topic=topic,
            payload=json.dumps(data).encode('utf-8'),
            qos=qos
        )


class MQTTClient:
    """MQTT client for drone telemetry."""
    
    def __init__(self, config: Optional[MQTTConfig] = None):
        self.config = config or MQTTConfig()
        
        self.connected = False
        self.client_id = f"skycore_{int(time.time())}"
        
        # Topics
        self.topics = TelemetryTopic(self.config.base_topic)
        
        # Subscriptions
        self.subscriptions: Dict[str, Callable] = {}
        
        # Message queues
        self.outgoing: List[TelemetryMessage] = []
        self.incoming: List[TelemetryMessage] = []
        
        # Statistics
        self.messages_sent = 0
        self.messages_received = 0
        self.last_ping = 0
    
    def connect(self) -> bool:
        """Connect to MQTT broker."""
        print(f"Connecting to MQTT broker {self.config.broker}:{self.config.port}...")
        
        # Simulated connection
        if self.config.username:
            print(f"  Authenticating as {self.config.username}")
        
        self.connected = True
        self.last_ping = time.time()
        
        print("MQTT connected")
        return True
    
    def disconnect(self) -> None:
        """Disconnect from broker."""
        self.connected = False
        print("MQTT disconnected")
    
    def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int = 0,
        retained: bool = False
    ) -> bool:
        """Publish message to topic.
        
        Args:
            topic: Topic path
            payload: Message payload
            qos: Quality of service level
            retained: Retain message
            
        Returns:
            True if published
        """
        if not self.connected:
            if not self.connect():
                return False
        
        message = TelemetryMessage(
            timestamp=time.time(),
            topic=topic,
            payload=payload,
            qos=qos,
            retained=retained
        )
        
        self.outgoing.append(message)
        self.messages_sent += 1
        
        return True
    
    def subscribe(
        self,
        topic: str,
        callback: Callable[[TelemetryMessage], None],
        qos: int = 0
    ) -> bool:
        """Subscribe to topic.
        
        Args:
            topic: Topic path (supports wildcards # and +)
            callback: Function to call on message
            qos: Quality of service level
            
        Returns:
            True if subscribed
        """
        if not self.connected:
            return False
        
        self.subscriptions[topic] = callback
        print(f"Subscribed to {topic}")
        
        return True
    
    def publish_telemetry(self, telemetry_data: Dict) -> bool:
        """Publish telemetry data.
        
        Args:
            telemetry_data: Dictionary with telemetry values
            
        Returns:
            True if published
        """
        payload = json.dumps(telemetry_data).encode('utf-8')
        
        return self.publish(
            self.topics.get_telemetry(),
            payload,
            qos=self.config.default_qos
        )
    
    def publish_gps(self, lat: float, lon: float, alt: float, 
                   satellites: int, hdop: float) -> bool:
        """Publish GPS data."""
        data = {
            'lat': lat,
            'lon': lon,
            'alt': alt,
            'satellites': satellites,
            'hdop': hdop,
            'timestamp': time.time()
        }
        
        payload = json.dumps(data).encode('utf-8')
        return self.publish(self.topics.get_gps(), payload)
    
    def publish_imu(self, accel: List[float], gyro: List[float], 
                   mag: List[float], temp: float) -> bool:
        """Publish IMU data."""
        data = {
            'accel': accel,
            'gyro': gyro,
            'mag': mag,
            'temp': temp,
            'timestamp': time.time()
        }
        
        payload = json.dumps(data).encode('utf-8')
        return self.publish(self.topics.get_imu(), payload)
    
    def publish_battery(self, voltage: float, current: float, 
                       remaining: int, temperature: float) -> bool:
        """Publish battery data."""
        data = {
            'voltage': voltage,
            'current': current,
            'remaining': remaining,
            'temp': temperature,
            'timestamp': time.time()
        }
        
        payload = json.dumps(data).encode('utf-8')
        return self.publish(self.topics.get_battery(), payload)
    
    def publish_attitude(self, roll: float, pitch: float, yaw: float) -> bool:
        """Publish attitude data."""
        data = {
            'roll': roll,
            'pitch': pitch,
            'yaw': yaw,
            'timestamp': time.time()
        }
        
        payload = json.dumps(data).encode('utf-8')
        return self.publish(self.topics.get_attitude(), payload)
    
    def publish_alert(self, level: str, message: str, data: Dict) -> bool:
        """Publish alert message.
        
        Args:
            level: Alert level (info, warning, error, critical)
            message: Alert message
            data: Additional alert data
        """
        alert = {
            'level': level,
            'message': message,
            'data': data,
            'timestamp': time.time()
        }
        
        payload = json.dumps(alert).encode('utf-8')
        return self.publish(self.topics.get_alerts(), payload, qos=1)
    
    def send_command(self, command: str, parameters: Dict) -> bool:
        """Send command to drone.
        
        Args:
            command: Command name
            parameters: Command parameters
            
        Returns:
            True if sent
        """
        cmd = {
            'command': command,
            'parameters': parameters,
            'timestamp': time.time()
        }
        
        payload = json.dumps(cmd).encode('utf-8')
        return self.publish(self.topics.get_command(), payload, qos=1)
    
    def subscribe_commands(self, callback: Callable[[Dict], None]) -> bool:
        """Subscribe to command topic."""
        def command_handler(msg: TelemetryMessage):
            try:
                cmd = json.loads(msg.payload.decode('utf-8'))
                callback(cmd)
            except json.JSONDecodeError:
                print("Failed to parse command JSON")
        
        return self.subscribe(self.topics.get_command(), command_handler, qos=1)
    
    def process_incoming(self) -> None:
        """Process incoming messages (callbacks)."""
        for topic, callback in self.subscriptions.items():
            # Simulate incoming messages
            pass
    
    def get_queue_size(self) -> int:
        """Get outgoing queue size."""
        return len(self.outgoing)
    
    def get_statistics(self) -> Dict:
        """Get communication statistics."""
        return {
            'connected': self.connected,
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received,
            'queue_size': len(self.outgoing),
            'subscriptions': len(self.subscriptions),
            'uptime': time.time() - self.last_ping if self.connected else 0
        }


class TelemetryBatcher:
    """Batch telemetry messages for efficient transmission."""
    
    def __init__(self, batch_size: int = 10, batch_timeout: float = 1.0):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        
        self.buffer: List[Dict] = []
        self.last_flush = time.time()
    
    def add(self, data: Dict) -> Optional[bytes]:
        """Add telemetry data to batch.
        
        Returns:
            Batch payload if batch is full, None otherwise
        """
        data['batch_time'] = time.time()
        self.buffer.append(data)
        
        # Check if batch is full
        if len(self.buffer) >= self.batch_size:
            return self.flush()
        
        # Check timeout
        if time.time() - self.last_flush > self.batch_timeout and self.buffer:
            return self.flush()
        
        return None
    
    def flush(self) -> Optional[bytes]:
        """Flush batch and return payload."""
        if not self.buffer:
            return None
        
        payload = json.dumps(self.buffer).encode('utf-8')
        self.buffer.clear()
        self.last_flush = time.time()
        
        return payload
    
    def get_pending(self) -> int:
        """Get number of pending items."""
        return len(self.buffer)


def demo_mqtt():
    """Demonstrate MQTT telemetry."""
    print("=" * 60)
    print("MQTT Telemetry Demo")
    print("=" * 60)
    
    # Create MQTT client
    config = MQTTConfig(
        broker="mqtt.example.com",
        port=1883,
        base_topic="skycore/drone001"
    )
    client = MQTTClient(config)
    
    # Connect
    print("\nConnecting...")
    connected = client.connect()
    print(f"  Connected: {connected}")
    
    # Subscribe to commands
    def handle_command(cmd: Dict):
        print(f"  Command received: {cmd}")
    
    client.subscribe_commands(handle_command)
    
    # Publish telemetry
    print("\n" + "=" * 40)
    print("Publishing Telemetry")
    print("=" * 40)
    
    # GPS
    client.publish_gps(32.0853, 34.7818, 50.0, satellites=12, hdop=1.0)
    print("  GPS published")
    
    # IMU
    client.publish_imu(
        accel=[0.1, -0.2, 9.8],
        gyro=[0.01, -0.01, 0.02],
        mag=[25, 5, 40],
        temp=35.0
    )
    print("  IMU published")
    
    # Battery
    client.publish_battery(voltage=12.6, current=5.0, remaining=75, temperature=28.0)
    print("  Battery published")
    
    # Attitude
    client.publish_attitude(roll=0.05, pitch=-0.03, yaw=1.23)
    print("  Attitude published")
    
    # Alert
    client.publish_alert("info", "Flight mode changed", {'mode': 'auto'})
    print("  Alert published")
    
    # Send command
    print("\n" + "=" * 40)
    print("Sending Command")
    print("=" * 40)
    
    success = client.send_command("goto", {'lat': 32.1, 'lon': 34.8, 'alt': 100})
    print(f"  Command sent: {success}")
    
    # Telemetry batching
    print("\n" + "=" * 40)
    print("Telemetry Batching")
    print("=" * 40)
    
    batcher = TelemetryBatcher(batch_size=5, batch_timeout=0.5)
    
    for i in range(10):
        data = {
            'sensor': 'imu',
            'value': i * 0.1,
            'sequence': i
        }
        
        batch = batcher.add(data)
        if batch:
            print(f"  Batch ready: {len(batch)} bytes")
            # In real implementation: client.publish("batch", batch)
    
    print(f"  Pending items: {batcher.get_pending()}")
    
    # Final flush
    final_batch = batcher.flush()
    if final_batch:
        print(f"  Final batch: {len(final_batch)} bytes")
    
    # Statistics
    print("\n" + "=" * 40)
    print("Statistics")
    print("=" * 40)
    
    stats = client.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    demo_mqtt()