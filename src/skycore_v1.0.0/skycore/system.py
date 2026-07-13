"""
SkyCore System Integration Layer
Ties all subsystems together for autonomous drone operations.
"""

import time
import threading
import json
import math
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import deque
import logging

# Import core subsystems - gracefully handle missing modules
try:
    from .navigation.kalman import KalmanFilter
except ImportError:
    KalmanFilter = None
    
try:
    from .navigation.ekf import ExtendedKalmanFilter
except ImportError:
    ExtendedKalmanFilter = None
    
try:
    from .navigation.ukf import UnscentedKalmanFilter
except ImportError:
    UnscentedKalmanFilter = None
    
try:
    from .navigation.aukf import AdaptiveUKF
except ImportError:
    AdaptiveUKF = None
    
try:
    from .navigation.ins import StrapdownINS
except ImportError:
    StrapdownINS = None
    
try:
    from .navigation.astar import AStarPlanner
except ImportError:
    AStarPlanner = None
    
try:
    from .navigation.rrt import RRTStarPlanner
except ImportError:
    RRTStarPlanner = None
    
try:
    from .navigation.geofence import GeofenceValidator, GeofenceConfig
except ImportError:
    GeofenceValidator = None
    GeofenceConfig = None

try:
    from .control.pid import PIDController, PIDConfig
except ImportError:
    PIDController = None
    PIDConfig = None
    
try:
    from .control.geometric import GeometricController
except ImportError:
    GeometricController = None
    
try:
    from .control.lqr import LQRController
except ImportError:
    LQRController = None
    
try:
    from .control.mpc import MPCController
except ImportError:
    MPCController = None
    
try:
    from .control.mixer import MotorMixer
except ImportError:
    MotorMixer = None
    
try:
    from .control.trajectory import TrajectoryGenerator
except ImportError:
    TrajectoryGenerator = None

try:
    from .sensors.imu import IMUSensor
except ImportError:
    IMUSensor = None
    
try:
    from .sensors.gnss import GNSSReceiver, RTKClient
except ImportError:
    GNSSReceiver = None
    RTKClient = None
    
try:
    from .sensors.barometer import Barometer
except ImportError:
    Barometer = None
    
try:
    from .sensors.compass import Magnetometer
except ImportError:
    Magnetometer = None
    
try:
    from .sensors.distance import DistanceSensor
except ImportError:
    DistanceSensor = None

try:
    from .communication.mavlink import MAVLinkHandler
except ImportError:
    MAVLinkHandler = None
    
try:
    from .communication.mqtt import MQTTBridge
except ImportError:
    MQTTBridge = None

try:
    from .perception.obstacle import ObstacleDetector
except ImportError:
    ObstacleDetector = None
    
try:
    from .perception.depth import DepthEstimator
except ImportError:
    DepthEstimator = None

try:
    from .swarm.coordinator import SwarmCoordinator
except ImportError:
    SwarmCoordinator = None

try:
    from .cuas.detector import CUASDetector
except ImportError:
    CUASDetector = None

try:
    from .voice.control import VoiceController
except ImportError:
    VoiceController = None

try:
    from .twins.physics import PhysicsTwin
except ImportError:
    PhysicsTwin = None

try:
    from .api.opensky import OpenSkyClient
except ImportError:
    OpenSkyClient = None
    
try:
    from .api.meteo import WeatherClient
except ImportError:
    WeatherClient = None
    
try:
    from .api.openrouter import OpenRouterClient
except ImportError:
    OpenRouterClient = None

from .state_machine import FlightStateMachine, FlightState, TriggerEvent, SafetyLimits
from .safety_monitor import SafetyMonitor, SafetyConfig, SafetyLevel


@dataclass
class SystemConfig:
    """Main system configuration"""
    config_file: str = "config/default.json"
    log_level: str = "INFO"
    telemetry_rate_hz: float = 10.0
    control_rate_hz: float = 100.0
    navigation_rate_hz: float = 50.0
    sensor_fusion_rate_hz: float = 100.0


@dataclass
class TelemetryData:
    """Current telemetry data snapshot"""
    timestamp: float
    position: Dict[str, float]
    velocity: Dict[str, float]
    attitude: Dict[str, float]
    battery: Dict[str, float]
    gps: Dict[str, Any]
    rc_channels: List[float]
    motor_outputs: List[float]
    state: str
    safety_level: str
    errors: List[str]


class SkyCoreSystem:
    """
    Main SkyCore system integration.
    
    Manages all subsystems and provides unified interface for:
    - Real-time navigation and control
    - Sensor fusion and state estimation
    - Path planning and trajectory execution
    - Safety monitoring and failsafe handling
    - Communication and telemetry
    - Mission execution
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize SkyCore system"""
        print("[SKYCORE] Initializing SkyCore Autonomous Drone Platform...")
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize logging
        self._setup_logging()
        
        # State management
        self.state_machine: Optional[FlightStateMachine] = None
        self.safety_monitor: Optional[SafetyMonitor] = None
        
        # Subsystems
        self.sensors: Dict[str, Any] = {}
        self.navigation: Dict[str, Any] = {}
        self.control: Dict[str, Any] = {}
        self.perception: Dict[str, Any] = {}
        self.communication: Dict[str, Any] = {}
        self.swarm: Optional[SwarmCoordinator] = None
        self.cuas: Optional[CUASDetector] = None
        self.voice: Optional[VoiceController] = None
        self.twin: Optional[PhysicsTwin] = None
        self.api: Dict[str, Any] = {}
        
        # Telemetry buffers
        self.telemetry_history: deque = deque(maxlen=1000)
        self.command_history: deque = deque(maxlen=100)
        
        # Current state
        self._current_position = {"lat": 0.0, "lon": 0.0, "alt": 0.0}
        self._current_velocity = {"north": 0.0, "east": 0.0, "down": 0.0}
        self._current_attitude = {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}
        self._current_battery = {"percent": 100.0, "voltage": 16.8, "current": 0.0}
        self._gps_data = {"satellites": 0, "hdop": 99.0, "fix_type": "none"}
        self._home_position = {"lat": 0.0, "lon": 0.0, "alt": 0.0}
        
        # Mission state
        self.current_mission: Optional[Dict] = None
        self.current_waypoint = 0
        self.mission_waypoints: List[Dict] = []
        
        # Thread safety
        self._lock = threading.RLock()
        self._running = False
        self._threads: List[threading.Thread] = []
        
        # Statistics
        self.start_time = time.time()
        self.cycle_count = 0
        self.error_count = 0
        
        # GCS data for web interface
        self.gcs_data = {
            "telemetry": {},
            "mission": {},
            "alerts": [],
            "logs": []
        }
        
        print("[SKYCORE] System configuration loaded")
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load configuration from file"""
        default_config = {
            "system": {
                "name": "SkyCore",
                "version": "1.0.0",
                "log_level": "INFO"
            },
            "navigation": {
                "aukf": {"enabled": True, "lambda": 3.0},
                "geofence": {"max_altitude_m": 120, "max_distance_m": 500}
            },
            "control": {
                "pid": {"altitude": {"kp": 1.5, "ki": 0.1, "kd": 0.5}}
            },
            "safety": {
                "battery_warning_percent": 30,
                "battery_critical_percent": 10
            }
        }
        
        if config_path:
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    return config
            except Exception as e:
                print(f"[SKYCORE] Failed to load config: {e}")
        
        return default_config
    
    def _setup_logging(self):
        """Setup logging system"""
        log_level = self.config.get("system", {}).get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        self.logger = logging.getLogger("SkyCore")
    
    def initialize(self) -> bool:
        """
        Initialize all subsystems.
        
        Returns:
            True if initialization successful
        """
        print("[SKYCORE] Initializing subsystems...")
        
        try:
            # Initialize state machine
            self._init_state_machine()
            
            # Initialize safety monitor
            self._init_safety_monitor()
            
            # Initialize sensors
            self._init_sensors()
            
            # Initialize navigation
            self._init_navigation()
            
            # Initialize control
            self._init_control()
            
            # Initialize perception
            self._init_perception()
            
            # Initialize communication
            self._init_communication()
            
            # Initialize C-UAS
            self._init_cuas()
            
            # Initialize voice
            self._init_voice()
            
            # Initialize digital twin
            self._init_twin()
            
            # Initialize APIs
            self._init_api()
            
            print("[SKYCORE] All subsystems initialized successfully")
            return True
            
        except Exception as e:
            print(f"[SKYCORE] Initialization failed: {e}")
            self.error_count += 1
            return False
    
    def _init_state_machine(self):
        """Initialize flight state machine"""
        safety_limits = SafetyLimits(
            max_altitude_m=self.config.get("navigation", {}).get("geofence", {}).get("max_altitude_m", 120),
            max_distance_m=self.config.get("navigation", {}).get("geofence", {}).get("max_distance_m", 500),
            battery_land_percent=self.config.get("safety", {}).get("battery_critical_percent", 10),
            battery_rtl_percent=self.config.get("safety", {}).get("battery_warning_percent", 20),
            min_gps_sats=8
        )
        
        self.state_machine = FlightStateMachine(safety_limits=safety_limits)
        self.state_machine.register_state_change_callback(self._on_state_change)
        self.state_machine.register_safety_callback(self._on_safety_alert)
        
        print("[SKYCORE] State machine initialized")
    
    def _init_safety_monitor(self):
        """Initialize safety monitor"""
        safety_config = SafetyConfig(
            battery_warning_percent=self.config.get("safety", {}).get("battery_warning_percent", 30),
            battery_critical_percent=self.config.get("safety", {}).get("battery_critical_percent", 10),
            max_altitude_m=self.config.get("navigation", {}).get("geofence", {}).get("max_altitude_m", 120),
            max_distance_m=self.config.get("navigation", {}).get("geofence", {}).get("max_distance_m", 500)
        )
        
        self.safety_monitor = SafetyMonitor(
            config=safety_config,
            home_position=self._home_position
        )
        self.safety_monitor.register_violation_callback(self._on_safety_violation)
        self.safety_monitor.register_emergency_callback(self._on_emergency)
        
        print("[SKYCORE] Safety monitor initialized")
    
    def _init_sensors(self):
        """Initialize all sensors"""
        # IMU
        if IMUSensor:
            imu_config = self.config.get("sensors", {}).get("imu", {})
            self.sensors["imu"] = IMUSensor(
                accel_range=imu_config.get("accel_range", 16.0),
                gyro_range=imu_config.get("gyro_range", 2000.0),
                sample_rate=imu_config.get("sample_rate_hz", 1000)
            )
        
        # GNSS
        if GNSSReceiver:
            gnss_config = self.config.get("sensors", {}).get("gnss", {})
            self.sensors["gnss"] = GNSSReceiver(
                min_satellites=gnss_config.get("min_satellites", 8)
            )
        
        # Barometer
        if Barometer:
            self.sensors["barometer"] = Barometer(
                ground_pressure=self.config.get("sensors", {}).get("barometer", {}).get("ground_pressure_pa", 101325)
            )
        
        # Magnetometer
        if Magnetometer:
            compass_config = self.config.get("sensors", {}).get("compass", {})
            self.sensors["compass"] = Magnetometer(
                magnetic_declination=math.radians(compass_config.get("magnetic_declination_deg", 4.5))
            )
        
        # Distance sensor (LIDAR)
        if DistanceSensor:
            lidar_config = self.config.get("sensors", {}).get("lidar", {})
            self.sensors["lidar"] = DistanceSensor(
                max_range=lidar_config.get("max_range_m", 30.0)
            )
        
        print("[SKYCORE] Sensors initialized")
    
    def _init_navigation(self):
        """Initialize navigation systems"""
        nav_config = self.config.get("navigation", {})
        
        # AUKF - primary filter
        if AdaptiveUKF and nav_config.get("aukf", {}).get("enabled", True):
            self.navigation["aukf"] = AdaptiveUKF(
                lambda_param=nav_config.get("aukf", {}).get("lambda", 3.0),
                n_sigma=nav_config.get("aukf", {}).get("n_sigma", 45)
            )
        
        # EKF - secondary
        if ExtendedKalmanFilter and nav_config.get("ekf", {}).get("enabled", False):
            self.navigation["ekf"] = ExtendedKalmanFilter(dim_x=16)
        
        # INS
        if StrapdownINS:
            self.navigation["ins"] = StrapdownINS()
        
        # Path planners
        if AStarPlanner:
            self.navigation["astar"] = AStarPlanner()
        if RRTStarPlanner:
            self.navigation["rrt"] = RRTStarPlanner()
        
        # Geofence
        if GeofenceValidator and GeofenceConfig:
            geofence_config = GeofenceConfig(
                max_altitude=nav_config.get("geofence", {}).get("max_altitude_m", 120),
                max_distance=nav_config.get("geofence", {}).get("max_distance_m", 500)
            )
            self.navigation["geofence"] = GeofenceValidator(geofence_config)
        
        print("[SKYCORE] Navigation systems initialized")
    
    def _init_control(self):
        """Initialize control systems"""
        control_config = self.config.get("control", {})
        
        # PID controllers
        if PIDController:
            pid_config = control_config.get("pid", {})
            self.control["altitude_pid"] = PIDController(
                kp=pid_config.get("altitude", {}).get("kp", 1.5),
                ki=pid_config.get("altitude", {}).get("ki", 0.1),
                kd=pid_config.get("altitude", {}).get("kd", 0.5)
            )
            self.control["position_pid"] = PIDController(
                kp=pid_config.get("position_xy", {}).get("kp", 1.2),
                ki=pid_config.get("position_xy", {}).get("ki", 0.05),
                kd=pid_config.get("position_xy", {}).get("kd", 0.3)
            )
            self.control["attitude_pid"] = PIDController(
                kp=pid_config.get("attitude", {}).get("kp", 3.0),
                ki=pid_config.get("attitude", {}).get("ki", 0.2),
                kd=pid_config.get("attitude", {}).get("kd", 0.5)
            )
        
        # Geometric controller
        if GeometricController and control_config.get("geometric", {}).get("enabled", True):
            self.control["geometric"] = GeometricController()
        
        # Motor mixer
        if MotorMixer:
            self.control["mixer"] = MotorMixer(frame_type="quad_x")
        
        # Trajectory generator
        if TrajectoryGenerator:
            self.control["trajectory"] = TrajectoryGenerator()
        
        print("[SKYCORE] Control systems initialized")
    
    def _init_perception(self):
        """Initialize perception systems"""
        perception_config = self.config.get("perception", {})
        
        # Obstacle detection
        if ObstacleDetector and perception_config.get("obstacle_detection", {}).get("enabled", False):
            self.perception["obstacle"] = ObstacleDetector(
                model_path=perception_config.get("obstacle_detection", {}).get("model_path"),
                confidence_threshold=perception_config.get("obstacle_detection", {}).get("confidence_threshold", 0.6)
            )
        
        # Depth estimation
        if DepthEstimator and perception_config.get("depth", {}).get("enabled", False):
            self.perception["depth"] = DepthEstimator(
                max_depth=perception_config.get("depth", {}).get("max_depth_m", 50.0)
            )
        
        print("[SKYCORE] Perception systems initialized")
    
    def _init_communication(self):
        """Initialize communication systems"""
        comm_config = self.config.get("communication", {})
        
        # MAVLink
        if MAVLinkHandler:
            mavlink_config = comm_config.get("mavlink", {})
            self.communication["mavlink"] = MAVLinkHandler(
                system_id=mavlink_config.get("system_id", 1),
                component_id=mavlink_config.get("component_id", 1)
            )
        
        # MQTT
        if MQTTBridge and comm_config.get("mqtt", {}).get("enabled", False):
            self.communication["mqtt"] = MQTTBridge(
                broker_host=comm_config.get("mqtt", {}).get("broker_host", "localhost"),
                broker_port=comm_config.get("mqtt", {}).get("broker_port", 1883),
                telemetry_topic=comm_config.get("mqtt", {}).get("telemetry_topic", "drone/telemetry")
            )
        
        print("[SKYCORE] Communication systems initialized")
    
    def _init_cuas(self):
        """Initialize C-UAS detection"""
        cuas_config = self.config.get("cuas", {})
        
        if CUASDetector and cuas_config.get("enabled", True):
            self.cuas = CUASDetector(
                detection_radius=cuas_config.get("detection_radius_m", 300.0),
                alert_radius=cuas_config.get("alert_radius_m", 200.0)
            )
            print("[SKYCORE] C-UAS system initialized")
    
    def _init_voice(self):
        """Initialize voice control"""
        voice_config = self.config.get("voice", {})
        
        if VoiceController and voice_config.get("enabled", True):
            self.voice = VoiceController(
                confidence_threshold=voice_config.get("confidence_threshold", 0.7),
                wake_word=voice_config.get("wake_word", "skycore")
            )
            print("[SKYCORE] Voice control initialized")
    
    def _init_twin(self):
        """Initialize digital twin"""
        twin_config = self.config.get("twin", {})
        
        if PhysicsTwin and twin_config.get("enabled", False):
            self.twin = PhysicsTwin(
                fidelity=twin_config.get("fidelity", "medium")
            )
            print("[SKYCORE] Digital twin initialized")
    
    def _init_api(self):
        """Initialize API clients"""
        api_config = self.config.get("api", {})
        
        # OpenSky
        if OpenSkyClient and api_config.get("opensky", {}).get("enabled", True):
            self.api["opensky"] = OpenSkyClient(
                api_url=api_config.get("opensky", {}).get("api_url", 
                    "https://opensky-network.org/api")
            )
        
        # Weather
        if WeatherClient and api_config.get("weather", {}).get("enabled", True):
            self.api["weather"] = WeatherClient(
                api_url=api_config.get("weather", {}).get("api_url",
                    "https://api.open-meteo.com/v1")
            )
        
        # OpenRouter
        if OpenRouterClient and api_config.get("openrouter", {}).get("enabled", True):
            self.api["openrouter"] = OpenRouterClient(
                api_key_env=api_config.get("openrouter", {}).get("api_key_env", "OPENROUTER_API_KEY")
            )
        
        print("[SKYCORE] API clients initialized")
    
    def _on_state_change(self, from_state, to_state, event):
        """Handle state machine changes"""
        self.logger.info(f"State: {from_state.value} -> {to_state.value}")
        self.gcs_data["logs"].append({
            "time": time.time(),
            "type": "state_change",
            "from": from_state.value,
            "to": to_state.value
        })
        
        # Update GCS data
        self.gcs_data["telemetry"]["state"] = to_state.value
    
    def _on_safety_alert(self, from_state, to_state, event):
        """Handle safety alerts"""
        self.logger.warning(f"Safety alert: {event.value}")
        self.gcs_data["alerts"].append({
            "time": time.time(),
            "severity": "warning",
            "message": f"Safety alert: {event.value}"
        })
    
    def _on_safety_violation(self, violation):
        """Handle safety violations"""
        self.logger.warning(f"Safety violation: {violation.message}")
        self.gcs_data["alerts"].append({
            "time": time.time(),
            "severity": violation.severity.value,
            "message": violation.message
        })
    
    def _on_emergency(self, violation):
        """Handle emergency situations"""
        self.logger.error(f"EMERGENCY: {violation.message}")
        self.gcs_data["alerts"].append({
            "time": time.time(),
            "severity": "emergency",
            "message": violation.message
        })
        self.error_count += 1
    
    def start(self):
        """Start the SkyCore system"""
        if self._running:
            print("[SKYCORE] System already running")
            return
        
        print("[SKYCORE] Starting SkyCore system...")
        self._running = True
        
        # Start main control loop
        control_thread = threading.Thread(target=self._control_loop, daemon=True)
        control_thread.start()
        self._threads.append(control_thread)
        
        # Start telemetry thread
        telemetry_thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        telemetry_thread.start()
        self._threads.append(telemetry_thread)
        
        # Start safety monitoring
        self.safety_monitor.start_monitoring()
        
        print("[SKYCORE] SkyCore system started successfully")
    
    def stop(self):
        """Stop the SkyCore system"""
        if not self._running:
            return
        
        print("[SKYCORE] Stopping SkyCore system...")
        self._running = False
        
        # Stop safety monitoring
        self.safety_monitor.stop_monitoring()
        
        # Wait for threads
        for thread in self._threads:
            thread.join(timeout=2.0)
        
        self._threads.clear()
        print("[SKYCORE] SkyCore system stopped")
    
    def _control_loop(self):
        """Main control loop at control_rate_hz"""
        rate = self.config.get("control_rate_hz", 100.0)
        dt = 1.0 / rate
        
        while self._running:
            try:
                start_time = time.time()
                
                # Read sensors
                self._read_sensors()
                
                # Update navigation
                self._update_navigation()
                
                # Run control
                self._run_control()
                
                # Check safety
                self._check_safety()
                
                # Execute mission if active
                if self.state_machine and self.state_machine.mission_active:
                    self._execute_mission_step()
                
                self.cycle_count += 1
                
                # Maintain rate
                elapsed = time.time() - start_time
                if elapsed < dt:
                    time.sleep(dt - elapsed)
                    
            except Exception as e:
                self.logger.error(f"Control loop error: {e}")
                self.error_count += 1
                time.sleep(0.01)
    
    def _telemetry_loop(self):
        """Telemetry broadcast loop"""
        rate = self.config.get("telemetry_rate_hz", 10.0)
        dt = 1.0 / rate
        
        while self._running:
            try:
                # Collect telemetry
                telemetry = self._collect_telemetry()
                
                # Store in history
                self.telemetry_history.append(telemetry)
                
                # Update GCS data
                self.gcs_data["telemetry"] = telemetry
                
                # Send via MQTT if enabled
                if "mqtt" in self.communication:
                    self.communication["mqtt"].publish_telemetry(telemetry)
                
                time.sleep(dt)
                
            except Exception as e:
                self.logger.error(f"Telemetry loop error: {e}")
                time.sleep(0.1)
    
    def _read_sensors(self):
        """Read all sensors"""
        with self._lock:
            # IMU
            if "imu" in self.sensors:
                imu_data = self.sensors["imu"].read()
                self.gcs_data["telemetry"]["imu"] = imu_data
            
            # GNSS
            if "gnss" in self.sensors:
                gnss_data = self.sensors["gnss"].read()
                self._gps_data = gnss_data
                if gnss_data.get("position"):
                    self._current_position.update(gnss_data["position"])
            
            # Barometer
            if "barometer" in self.sensors:
                baro_data = self.sensors["barometer"].read()
                if "altitude" in baro_data:
                    self._current_position["alt"] = baro_data["altitude"]
            
            # Battery (simulated)
            self._current_battery["percent"] = max(0, self._current_battery["percent"] - 0.001)
    
    def _update_navigation(self):
        """Update navigation estimates"""
        with self._lock:
            # Run AUKF
            if "aukf" in self.navigation:
                measurements = {
                    "gps": self._gps_data,
                    "barometer": self._current_position.get("alt", 0)
                }
                state = self.navigation["aukf"].update(measurements, 0.01)
                if state:
                    self._current_position["lat"] = state.get("lat", self._current_position["lat"])
                    self._current_position["lon"] = state.get("lon", self._current_position["lon"])
                    self._current_velocity = {
                        "north": state.get("vn", 0),
                        "east": state.get("ve", 0),
                        "down": state.get("vd", 0)
                    }
            
            # Update INS
            if "ins" in self.navigation:
                ins_data = self.navigation["ins"].update(
                    accel=[0, 0, -9.81],
                    gyro=[0, 0, 0],
                    dt=0.01
                )
                if ins_data:
                    self._current_attitude = ins_data.get("attitude", self._current_attitude)
    
    def _run_control(self):
        """Run control algorithms"""
        with self._lock:
            state = self.state_machine.state if self.state_machine else FlightState.DISARMED
            
            if state == FlightState.DISARMED:
                motor_outputs = [0, 0, 0, 0]
            elif state == FlightState.ARMED:
                motor_outputs = [900, 900, 900, 900]  # Idle
            elif state in [FlightState.TAKEOFF, FlightState.HOLD, FlightState.AUTO, FlightState.MANUAL]:
                # Run altitude PID
                target_alt = 20.0  # Default hold altitude
                current_alt = self._current_position.get("alt", 0)
                alt_output = self.control["altitude_pid"].compute(target_alt, current_alt, 0.01)
                
                # Mix for motors (simplified)
                motor_outputs = self.control["mixer"].mix(
                    thrust=1000 + alt_output * 100,
                    roll=0,
                    pitch=0,
                    yaw=0
                )
            else:
                motor_outputs = [0, 0, 0, 0]
            
            self.gcs_data["telemetry"]["motor_outputs"] = motor_outputs
    
    def _check_safety(self):
        """Run safety checks"""
        with self._lock:
            # Update safety monitor state
            self.safety_monitor.update_state({
                "position": self._current_position,
                "battery": self._current_battery,
                "gps": self._gps_data,
                "rc": {"connected": True, "last_signal": time.time()},
                "gcs": {"connected": True, "last_signal": time.time()}
            })
            
            # Check all
            violations = self.safety_monitor.check_all()
            
            # Update state machine telemetry
            if self.state_machine:
                self.state_machine.update_telemetry(
                    position=self._current_position,
                    battery_percent=self._current_battery["percent"],
                    gps_satellites=self._gps_data.get("satellites", 0)
                )
    
    def _execute_mission_step(self):
        """Execute current mission step"""
        if not self.mission_waypoints or self.current_waypoint >= len(self.mission_waypoints):
            # Mission complete
            if self.state_machine:
                self.state_machine.mission_active = False
                self.state_machine.trigger(TriggerEvent.MISSION_END)
            return
        
        # Get current waypoint
        wp = self.mission_waypoints[self.current_waypoint]
        
        # Check if reached
        distance = self._calculate_distance(
            self._current_position["lat"], self._current_position["lon"],
            wp["lat"], wp["lon"]
        )
        
        if distance < 3.0:  # Acceptance radius
            self.current_waypoint += 1
            self.logger.info(f"Waypoint {self.current_waypoint} reached")
    
    def _collect_telemetry(self) -> Dict:
        """Collect current telemetry data"""
        with self._lock:
            return {
                "timestamp": time.time(),
                "position": self._current_position.copy(),
                "velocity": self._current_velocity.copy(),
                "attitude": self._current_attitude.copy(),
                "battery": self._current_battery.copy(),
                "gps": self._gps_data.copy(),
                "state": self.state_machine.state.value if self.state_machine else "unknown",
                "safety_level": self.safety_monitor.get_status()["level"].value if self.safety_monitor else "ok",
                "waypoint": self.current_waypoint,
                "total_waypoints": len(self.mission_waypoints)
            }
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2) -> float:
        """Calculate distance between two points"""
        import math
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    # Public API
    
    def arm(self) -> bool:
        """Arm the drone"""
        if self.state_machine and self.state_machine.can_arm():
            if self.safety_monitor.is_safe_to_takeoff():
                self.state_machine.trigger(TriggerEvent.ARM_REQUEST)
                return True
            else:
                self.logger.warning("Cannot arm: safety check failed")
                return False
        return False
    
    def disarm(self) -> bool:
        """Disarm the drone"""
        if self.state_machine and self.state_machine.can_disarm():
            self.state_machine.trigger(TriggerEvent.DISARM_REQUEST)
            return True
        return False
    
    def takeoff(self, altitude: float = 10.0) -> bool:
        """Initiate takeoff"""
        if self.state_machine and self.state_machine.can_takeoff():
            self.state_machine.trigger(TriggerEvent.TAKEOFF_CMD)
            self.target_altitude = altitude
            return True
        return False
    
    def land(self) -> bool:
        """Initiate landing"""
        if self.state_machine:
            return self.state_machine.trigger(TriggerEvent.LAND_CMD)
        return False
    
    def rtl(self) -> bool:
        """Return to launch"""
        if self.state_machine:
            return self.state_machine.trigger(TriggerEvent.RTL_CMD)
        return False
    
    def emergency_land(self) -> bool:
        """Emergency landing"""
        if self.state_machine:
            return self.state_machine.trigger(TriggerEvent.E_LAND_CMD)
        return False
    
    def emergency_stop(self):
        """Emergency stop"""
        if self.state_machine:
            self.state_machine.emergency_stop()
    
    def load_mission(self, mission_data: Dict) -> bool:
        """Load a mission"""
        try:
            self.mission_waypoints = mission_data.get("waypoints", [])
            self.current_waypoint = 0
            self.current_mission = mission_data
            
            if self.state_machine:
                self.state_machine.total_waypoints = len(self.mission_waypoints)
                self.state_machine.mission_active = False
            
            self.logger.info(f"Mission loaded: {len(self.mission_waypoints)} waypoints")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load mission: {e}")
            return False
    
    def start_mission(self) -> bool:
        """Start loaded mission"""
        if not self.mission_waypoints:
            self.logger.warning("No mission loaded")
            return False
        
        if self.state_machine:
            self.state_machine.mission_active = True
            self.state_machine.trigger(TriggerEvent.MISSION_START)
            return True
        return False
    
    def pause_mission(self) -> bool:
        """Pause current mission"""
        if self.state_machine:
            return self.state_machine.trigger(TriggerEvent.PAUSE)
        return False
    
    def resume_mission(self) -> bool:
        """Resume paused mission"""
        if self.state_machine:
            return self.state_machine.trigger(TriggerEvent.MISSION_START)
        return False
    
    def set_home(self, lat: float, lon: float, alt: float = 0.0):
        """Set home position"""
        self._home_position = {"lat": lat, "lon": lon, "alt": alt}
        if self.safety_monitor:
            self.safety_monitor.set_home_position(lat, lon, alt)
        self.logger.info(f"Home set: {lat}, {lon}, {alt}m")
    
    def get_state(self) -> Dict:
        """Get current system state"""
        state = {
            "system": {
                "running": self._running,
                "uptime_sec": time.time() - self.start_time,
                "cycle_count": self.cycle_count,
                "error_count": self.error_count
            },
            "flight": self.state_machine.get_state_info() if self.state_machine else {},
            "safety": self.safety_monitor.get_status() if self.safety_monitor else {},
            "position": self._current_position.copy(),
            "velocity": self._current_velocity.copy(),
            "attitude": self._current_attitude.copy(),
            "battery": self._current_battery.copy(),
            "gps": self._gps_data.copy(),
            "mission": {
                "active": self.state_machine.mission_active if self.state_machine else False,
                "waypoint": self.current_waypoint,
                "total_waypoints": len(self.mission_waypoints)
            }
        }
        return state
    
    def get_gcs_data(self) -> Dict:
        """Get data for GCS web interface"""
        return self.gcs_data
    
    def send_command(self, command: str, params: Optional[Dict] = None) -> bool:
        """Send command to system"""
        self.command_history.append({
            "time": time.time(),
            "command": command,
            "params": params or {}
        })
        
        # Handle commands
        if command == "arm":
            return self.arm()
        elif command == "disarm":
            return self.disarm()
        elif command == "takeoff":
            return self.takeoff(params.get("altitude", 10) if params else 10)
        elif command == "land":
            return self.land()
        elif command == "rtl":
            return self.rtl()
        elif command == "e_stop":
            self.emergency_stop()
            return True
        elif command == "load_mission":
            return self.load_mission(params or {})
        elif command == "start_mission":
            return self.start_mission()
        elif command == "pause_mission":
            return self.pause_mission()
        elif command == "resume_mission":
            return self.resume_mission()
        elif command == "set_home":
            if params:
                self.set_home(params["lat"], params["lon"], params.get("alt", 0))
            return True
        
        return False


# Standalone function for quick testing
def create_system(config_path: Optional[str] = None) -> SkyCoreSystem:
    """Create and initialize a new SkyCore system"""
    system = SkyCoreSystem(config_path)
    if system.initialize():
        return system
    return None