"""
SkyCore ROS2-Style Architecture (inspired by professional robotics frameworks)
Node-based, topic-based communication for maximum modularity
"""

from typing import Callable, Dict, Any
import asyncio

class Node:
    """ROS2-style Node for SkyCore"""
    def __init__(self, name: str):
        self.name = name
        self.subscribers: Dict[str, list] = {}
        self.publishers: Dict[str, list] = {}

    def create_publisher(self, topic: str):
        if topic not in self.publishers:
            self.publishers[topic] = []
        return self

    def create_subscription(self, topic: str, callback: Callable):
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)
        return self

    async def publish(self, topic: str, message: Any):
        if topic in self.subscribers:
            for callback in self.subscribers[topic]:
                await callback(message) if asyncio.iscoroutinefunction(callback) else callback(message)

class SecurityNode(Node):
    """Security-specific node"""
    def __init__(self):
        super().__init__("security_node")
        self.create_subscription("threat_detected", self.on_threat)
        self.create_publisher("command_to_drones")

    async def on_threat(self, threat: dict):
        print(f"[{self.name}] Received threat: {threat}")
        await self.publish("command_to_drones", {"action": "defend", "threat": threat})
