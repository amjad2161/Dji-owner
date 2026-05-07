"""Abstract drone interface. Every backend implements this.

The contract is intentionally narrow: connect, takeoff, fly, look, shoot,
land. Higher-level functionality (missions, vision, video) is built on top
of this interface so it works against any backend.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from skycore.core.types import GeoPoint, Telemetry


class Drone(ABC):
    """Abstract drone. Subclasses provide a concrete backend."""

    name: str = "abstract"

    @abstractmethod
    async def connect(self) -> None:
        """Open the link to the drone. Idempotent."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the link."""

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    async def takeoff(self, altitude_m: float = 5.0) -> None: ...

    @abstractmethod
    async def land(self) -> None: ...

    @abstractmethod
    async def return_to_home(self) -> None: ...

    @abstractmethod
    async def goto(self, point: GeoPoint, speed_mps: float = 5.0) -> None: ...

    @abstractmethod
    async def set_velocity(
        self, vx: float, vy: float, vz: float, yaw_rate: float = 0.0
    ) -> None:
        """Direct velocity command (m/s). vx forward, vy right, vz down. yaw_rate deg/s."""

    @abstractmethod
    async def set_yaw(self, yaw_deg: float) -> None: ...

    @abstractmethod
    async def set_gimbal(self, pitch_deg: float) -> None: ...

    @abstractmethod
    async def take_photo(self) -> str:
        """Trigger a photo. Returns a path / URI to the file."""

    @abstractmethod
    async def start_recording(self) -> None: ...

    @abstractmethod
    async def stop_recording(self) -> None: ...

    @abstractmethod
    async def get_telemetry(self) -> Telemetry: ...

    @abstractmethod
    def telemetry_stream(self) -> AsyncIterator[Telemetry]:
        """Continuous telemetry stream. Async iterator."""

    # Convenience

    async def __aenter__(self) -> "Drone":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await self.land()
        except Exception:
            pass
        await self.disconnect()
