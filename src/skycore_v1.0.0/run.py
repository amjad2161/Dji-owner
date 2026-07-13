# SkyCore Drone Operating System
# Version 1.0.0

"""
SkyCore - Autonomous Drone Operations Platform

Usage:
    python run.py                    # Start in CLI mode
    python run.py --gui              # Start with web GUI
    python run.py --simulator        # Start with drone simulator
    python run.py --tello            # Connect to Tello drone
    python run.py --mavlink           # Connect via MAVLink

For full documentation, see README.md
"""

import sys
import asyncio
import argparse
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger("skycore")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="SkyCore - Autonomous Drone Operations Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    # Mode options
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--simulator",
        action="store_true",
        help="Run with drone simulator",
    )
    mode.add_argument(
        "--tello",
        action="store_true",
        help="Connect to Tello drone",
    )
    mode.add_argument(
        "--mavlink",
        action="store_true",
        help="Connect via MAVLink (PX4/ArduPilot)",
    )
    mode.add_argument(
        "--dji",
        action="store_true",
        help="Connect to DJI drone",
    )
    
    # GUI options
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Start web-based GCS interface",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Web server port (default: 8080)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Web server host (default: 127.0.0.1)",
    )
    
    # Development options
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Development mode with debug logging",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output",
    )
    
    # Mission options
    parser.add_argument(
        "--mission",
        type=str,
        help="Load mission from Litchi CSV file",
    )
    parser.add_argument(
        "--takeoff",
        type=float,
        help="Takeoff altitude in meters",
    )
    
    return parser.parse_args()


async def run_simulator_mode():
    """Run with drone simulator."""
    log.info("Starting SkyCore in SIMULATOR mode")
    
    from skycore.adapters.simulator import SimulatorDrone
    from skycore.core.types import GeoPoint
    from skycore.missions.litchi import LitchiMission
    from skycore.control.pid import PIDController
    from skycore.navigation.kalman import KalmanFilter
    
    # Create simulator drone
    drone = SimulatorDrone(home=GeoPoint(37.7749, -122.4194, 0.0))
    
    log.info("Connecting to simulator...")
    await drone.connect()
    log.info(f"Connected: {drone.is_connected}")
    
    # Create navigation components
    kf = KalmanFilter(dim_x=6, dim_z=3)
    pid_alt = PIDController(kp=1.0, ki=0.1, kd=0.3)
    pid_yaw = PIDController(kp=2.0, ki=0.0, kd=0.1)
    
    log.info("Navigation components initialized")
    
    # Takeoff
    log.info("Taking off to 20m...")
    await drone.takeoff(20.0)
    log.info(f"Altitude: {drone.position.alt}m")
    
    # Hover for a bit
    await asyncio.sleep(2)
    
    # Get telemetry
    telemetry = await drone.get_telemetry()
    log.info(
        f"Position: lat={telemetry.position.lat:.6f}, "
        f"lon={telemetry.position.lon:.6f}, "
        f"alt={telemetry.position.alt:.1f}m"
    )
    
    # Land
    log.info("Landing...")
    await drone.land()
    
    # Cleanup
    await drone.disconnect()
    log.info("Simulator session complete")
    
    return 0


async def run_tello_mode():
    """Run with Tello drone."""
    log.info("Starting SkyCore with Tello drone...")
    
    try:
        from skycore.adapters.tello import TelloDrone
        
        drone = TelloDrone()
        await drone.connect()
        await drone.takeoff(20)
        
        log.info("Tello connected and flown")
        
        await drone.land()
        await drone.disconnect()
        
    except ImportError:
        log.error("djitellopy not installed. Run: pip install djitellopy")
        return 1
    except Exception as e:
        log.error(f"Tello connection failed: {e}")
        return 1
    
    return 0


async def run_mavlink_mode():
    """Run with MAVLink drone (PX4/ArduPilot)."""
    log.info("Starting SkyCore with MAVLink drone...")
    
    try:
        from skycore.adapters.mavlink import MavlinkDrone
        
        drone = MavlinkDrone(connection_url="udp://:14540")
        await drone.connect()
        
        log.info("MAVLink connected")
        
        # ... rest of MAVLink operations
        
    except ImportError:
        log.error("mavsdk not installed. Run: pip install mavsdk")
        return 1
    except Exception as e:
        log.error(f"MAVLink connection failed: {e}")
        return 1
    
    return 0


async def run_gui_mode(host: str, port: int):
    """Run with web GUI."""
    log.info(f"Starting SkyCore GUI on {host}:{port}")
    
    try:
        # Import web app
        from skycore.web.src.app import create_app
        
        import uvicorn
        
        config = uvicorn.Config(
            "skycore.web.src.app:create_app",
            host=host,
            port=port,
            reload=False,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()
        
    except ImportError as e:
        log.error(f"Web dependencies not installed: {e}")
        log.info("Run: pip install fastapi uvicorn")
        return 1
    except Exception as e:
        log.error(f"GUI startup failed: {e}")
        return 1
    
    return 0


async def run_mission_mode(mission_path: str):
    """Run a mission from Litchi CSV."""
    log.info(f"Loading mission: {mission_path}")
    
    from skycore.adapters.simulator import SimulatorDrone
    from skycore.core.types import GeoPoint
    from skycore.missions.litchi import LitchiMission
    from skycore.missions.executor import MissionExecutor
    
    # Load mission
    mission = LitchiMission.from_csv(mission_path)
    log.info(f"Mission loaded: {len(mission.waypoints)} waypoints")
    
    # Create executor with simulator
    drone = SimulatorDrone()
    executor = MissionExecutor(drone)
    
    # Load mission
    from skycore.missions.executor import MissionWaypoint
    
    waypoints = [
        MissionWaypoint(
            lat=wp.latitude,
            lon=wp.longitude,
            alt=wp.altitude,
            speed_mps=wp.speed if wp.speed > 0 else 5.0,
        )
        for wp in mission.waypoints
    ]
    
    executor.load_mission(waypoints)
    
    # Execute
    await drone.connect()
    await drone.takeoff(30.0)
    
    await executor.start()
    
    # Wait for completion
    while executor.state.value not in ["completed", "aborted"]:
        await asyncio.sleep(1)
        status = executor.get_status()
        log.info(f"Progress: {status.progress_pct:.1f}%")
    
    # Land and disconnect
    await drone.land()
    await drone.disconnect()
    
    return 0


def main():
    """Main entry point."""
    args = parse_args()
    
    # Configure logging level
    if args.verbose or args.dev:
        logging.getLogger().setLevel(logging.DEBUG)
        log.debug("Debug logging enabled")
    
    # Select mode
    try:
        if args.gui:
            return asyncio.run(run_gui_mode(args.host, args.port))
        elif args.mission:
            return asyncio.run(run_mission_mode(args.mission))
        elif args.simulator:
            return asyncio.run(run_simulator_mode())
        elif args.tello:
            return asyncio.run(run_tello_mode())
        elif args.mavlink:
            return asyncio.run(run_mavlink_mode())
        else:
            # Default: simulator mode
            return asyncio.run(run_simulator_mode())
            
    except KeyboardInterrupt:
        log.info("Shutdown requested")
        return 0
    except Exception as e:
        log.error(f"Fatal error: {e}")
        if args.dev:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())