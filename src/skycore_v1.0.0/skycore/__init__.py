"""
SkyCore - Autonomous Drone Operations Platform
Version: 1.0.0
Comprehensive autonomous drone system with 22-state AUKF navigation,
multi-controller support, C-UAS detection, swarm coordination, and GCS web interface.
"""

__version__ = "1.0.0"
__author__ = "SkyCore Team"

# Core system imports
from skycore.system import SkyCoreSystem, create_system
from skycore.state_machine import (
    FlightStateMachine, 
    FlightState, 
    TriggerEvent, 
    SafetyLimits,
    ModeController,
    FailsafeManager
)
from skycore.safety_monitor import (
    SafetyMonitor,
    SafetyConfig,
    SafetyLevel,
    ViolationType,
    SafetyViolation,
    GeofenceValidator
)

# Navigation imports
try:
    from skycore.navigation.kalman import KalmanFilter
    from skycore.navigation.ekf import ExtendedKalmanFilter
    from skycore.navigation.ukf import UnscentedKalmanFilter
    from skycore.navigation.aukf import AdaptiveUKF
    from skycore.navigation.ins import StrapdownINS
    from skycore.navigation.astar import AStarPlanner
    from skycore.navigation.rrt import RRTStarPlanner
    from skycore.navigation.geofence import GeofenceValidator, GeofenceConfig
    NAVIGATION_AVAILABLE = True
except ImportError:
    NAVIGATION_AVAILABLE = False

# Control imports
try:
    from skycore.control.pid import PIDController, PIDConfig
    from skycore.control.geometric import GeometricController
    from skycore.control.lqr import LQRController
    from skycore.control.mpc import MPCController
    from skycore.control.mixer import MotorMixer
    from skycore.control.trajectory import TrajectoryGenerator
    CONTROL_AVAILABLE = True
except ImportError:
    CONTROL_AVAILABLE = False

# Sensor imports
try:
    from skycore.sensors.imu import IMUSensor
    from skycore.sensors.gnss import GNSSReceiver, RTKClient
    from skycore.sensors.barometer import Barometer
    from skycore.sensors.compass import Magnetometer
    from skycore.sensors.distance import DistanceSensor
    SENSORS_AVAILABLE = True
except ImportError:
    SENSORS_AVAILABLE = False

__all__ = [
    # Version info
    "__version__",
    
    # Core system
    "SkyCoreSystem",
    "create_system",
    
    # State machine
    "FlightStateMachine",
    "FlightState",
    "TriggerEvent",
    "SafetyLimits",
    "ModeController",
    "FailsafeManager",
    
    # Safety
    "SafetyMonitor",
    "SafetyConfig",
    "SafetyLevel",
    "ViolationType",
    "SafetyViolation",
    "GeofenceValidator",
    
    # Version
    "NAVIGATION_AVAILABLE",
    "CONTROL_AVAILABLE",
    "SENSORS_AVAILABLE",
]