"""SkyCore — unified drone operations platform.

A single Python API for flight control, missions, vision, video, and
analytics across DJI, MAVLink (PX4 / ArduPilot), Tello, and a built-in
simulator. The simulator backend works without any hardware so you can
develop and test the entire stack on a laptop.

Quick example:

    import asyncio
    from skycore import SimulatorDrone, GeoPoint

    async def main():
        drone = SimulatorDrone(home=GeoPoint(37.7749, -122.4194))
        await drone.connect()
        await drone.takeoff(altitude_m=10)
        await drone.goto(GeoPoint(37.7755, -122.4194, 10))
        await drone.return_to_home()
        await drone.disconnect()

    asyncio.run(main())
"""
__version__ = "0.1.0"

from skycore.core.types import (
    GeoPoint,
    Telemetry,
    MissionStep,
    FlightMode,
    FlightStatus,
    GeofenceConfig,
)
from skycore.core.drone import Drone
from skycore.adapters.simulator import SimulatorDrone

__all__ = [
    "Drone",
    "SimulatorDrone",
    "GeoPoint",
    "Telemetry",
    "MissionStep",
    "FlightMode",
    "FlightStatus",
    "GeofenceConfig",
]
