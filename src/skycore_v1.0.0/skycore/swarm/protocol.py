"""
Swarm Communication Protocol
MAVLink-based peer-to-peer communication for drone swarms
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import struct

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Swarm message types."""
    POSITION = 1
    VELOCITY = 2
    COMMAND = 3
    ACK = 4
    HEARTBEAT = 5
    FORMATION = 6
    EMERGENCY = 7
    TELEMETRY = 8


@dataclass 
class DroneNode:
    """Swarm drone node representation."""
    drone_id: int
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    battery_percent: float = 100.0
    is_leader: bool = False
    last_seen: float = 0.0
    
    @property
    def is_online(self) -> bool:
        import time
        return time.time() - self.last_seen < 5.0  # 5 second timeout


@dataclass
class SwarmMessage:
    """Swarm communication message."""
    sender_id: int
    message_type: MessageType
    payload: bytes
    timestamp: float
    sequence: int = 0
    
    def encode(self) -> bytes:
        """Encode message to bytes."""
        header = struct.pack('!IBBH', self.sender_id, self.message_type.value, 
                             self.sequence, len(self.payload))
        return header + self.payload
    
    @classmethod
    def decode(cls, data: bytes) -> 'SwarmMessage':
        """Decode message from bytes."""
        sender_id, msg_type, seq, payload_len = struct.unpack('!IBBH', data[:8])
        payload = data[8:8+payload_len]
        return cls(
            sender_id=sender_id,
            message_type=MessageType(msg_type),
            payload=payload,
            timestamp=0.0,  # Will be set by receiver
            sequence=seq
        )


class SwarmProtocol:
    """
    Swarm communication protocol handler.
    
    Features:
    - Multi-drone communication
    - Message acknowledgment
    - Formation coordination
    - Emergency broadcast
    """
    
    def __init__(self, drone_id: int, network_id: int = 1):
        self.drone_id = drone_id
        self.network_id = network_id
        self.peer_ids: Set[int] = set()
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.pending_acks: Dict[int, asyncio.Future] = {}
        self.sequence_counter = 0
        self._running = False
        self._listeners: List[callable] = []
    
    async def add_peer(self, peer_id: int):
        """Add a peer drone to the swarm."""
        self.peer_ids.add(peer_id)
        logger.info(f"Added peer {peer_id} to swarm")
    
    async def remove_peer(self, peer_id: int):
        """Remove a peer drone from the swarm."""
        self.peer_ids.discard(peer_id)
        logger.info(f"Removed peer {peer_id} from swarm")
    
    async def send_message(self, peer_id: int, msg_type: MessageType, payload: bytes) -> bool:
        """Send message to a peer."""
        msg = SwarmMessage(
            sender_id=self.drone_id,
            message_type=msg_type,
            payload=payload,
            timestamp=asyncio.get_event_loop().time(),
            sequence=self.sequence_counter
        )
        self.sequence_counter += 1
        
        try:
            await self._send_raw(peer_id, msg.encode())
            return True
        except Exception as e:
            logger.error(f"Send error to peer {peer_id}: {e}")
            return False
    
    async def broadcast(self, msg_type: MessageType, payload: bytes) -> int:
        """Broadcast message to all peers."""
        success_count = 0
        for peer_id in self.peer_ids:
            if await self.send_message(peer_id, msg_type, payload):
                success_count += 1
        return success_count
    
    async def emergency_broadcast(self, message: str):
        """Broadcast emergency message to all peers."""
        payload = message.encode('utf-8')
        count = await self.broadcast(MessageType.EMERGENCY, payload)
        logger.warning(f"Emergency broadcast sent to {count} peers")
        return count
    
    def on_message(self, callback: callable):
        """Register message listener."""
        self._listeners.append(callback)
    
    async def _process_incoming(self, data: bytes, from_peer: int):
        """Process incoming message."""
        try:
            msg = SwarmMessage.decode(data)
            
            # Notify listeners
            for listener in self._listeners:
                try:
                    await listener(msg, from_peer)
                except Exception as e:
                    logger.error(f"Listener error: {e}")
            
            # Send ACK for reliable messages
            if msg.message_type in [MessageType.COMMAND, MessageType.EMERGENCY]:
                ack_payload = struct.pack('!I', msg.sequence)
                await self._send_raw(from_peer, SwarmMessage(
                    sender_id=self.drone_id,
                    message_type=MessageType.ACK,
                    payload=ack_payload,
                    timestamp=0.0,
                    sequence=msg.sequence
                ).encode())
                
        except Exception as e:
            logger.error(f"Message processing error: {e}")
    
    async def _send_raw(self, peer_id: int, data: bytes):
        """Send raw bytes to peer (implement with actual network layer)."""
        # Placeholder - implement with actual network transport
        pass
    
    def get_peer_count(self) -> int:
        """Get number of connected peers."""
        return len(self.peer_ids)
    
    def get_statistics(self) -> Dict:
        """Get protocol statistics."""
        return {
            'drone_id': self.drone_id,
            'network_id': self.network_id,
            'peer_count': len(self.peer_ids),
            'sequence': self.sequence_counter
        }