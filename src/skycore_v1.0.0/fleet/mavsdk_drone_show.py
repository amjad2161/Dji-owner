"""
SkyCore MAVSDK Drone Show Fleet Operations
Based on alireza787b/mavsdk_drone_show patterns

Features:
- Fleet formation control
- Synchronized choreography
- Real-time formation adjustments
- Emergency protocols
- LED pattern programming
"""

import time
import math
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class FormationType(Enum):
    """Drone show formation types"""
    LINE = "line"
    GRID = "grid"
    CIRCLE = "circle"
    HEART = "heart"
    STAR = "star"
    WORD = "word"
    CUSTOM = "custom"


@dataclass
class DroneState:
    """Fleet drone state"""
    id: int
    position: Tuple[float, float, float]  # x, y, z in meters
    target_position: Tuple[float, float, float]
    velocity: Tuple[float, float, float] = (0, 0, 0)
    battery: float = 100.0
    status: str = "idle"
    led_color: Tuple[int, int, int] = (0, 255, 0)  # RGB


@dataclass
class FormationPoint:
    """Point in a formation"""
    drone_id: int
    position: Tuple[float, float, float]
    transition_time: float = 0.0


@dataclass
class ShowSequence:
    """Drone show sequence"""
    name: str
    formations: List[Dict[str, List[FormationPoint]]]
    duration: float
    music_sync: bool = False
    bpm: int = 120


class FleetManager:
    """
    MAVSDK-style fleet manager for drone shows
    Handles multiple drones with synchronized control
    """
    
    def __init__(self, max_drones: int = 50):
        self.max_drones = max_drones
        self.drones: Dict[int, DroneState] = {}
        self.leader_id: Optional[int] = None
        
        # Show parameters
        self.formation_update_rate = 20  # Hz
        self.position_tolerance = 0.3  # meters
        self.sync_tolerance = 0.1  # seconds
        
        # Active sequence
        self.current_sequence: Optional[ShowSequence] = None
        self.sequence_start_time = 0.0
        
        logging.info(f"Fleet manager initialized for up to {max_drones} drones")
        
    def add_drone(self, drone_id: int) -> bool:
        """Add drone to fleet"""
        if drone_id in self.drones:
            logging.warning(f"Drone {drone_id} already in fleet")
            return False
            
        if len(self.drones) >= self.max_drones:
            logging.error("Fleet full")
            return False
            
        self.drones[drone_id] = DroneState(
            id=drone_id,
            position=(0, 0, 0),
            target_position=(0, 0, 0),
            status="idle"
        )
        
        logging.info(f"Added drone {drone_id} to fleet")
        return True
        
    def remove_drone(self, drone_id: int) -> bool:
        """Remove drone from fleet"""
        if drone_id in self.drones:
            del self.drones[drone_id]
            if self.leader_id == drone_id:
                self.leader_id = None
            return True
        return False
        
    def set_leader(self, drone_id: int):
        """Set leader drone for formation reference"""
        if drone_id in self.drones:
            self.leader_id = drone_id
            logging.info(f"Drone {drone_id} is now leader")
            
    def generate_formation(
        self,
        formation_type: FormationType,
        center: Tuple[float, float, float] = (0, 0, 20),
        **kwargs
    ) -> Dict[int, Tuple[float, float, float]]:
        """
        Generate target positions for formation
        
        Args:
            formation_type: Type of formation
            center: Formation center position
            **kwargs: Additional parameters (spacing, size, etc.)
            
        Returns:
            Dict of drone_id -> target position
        """
        n_drones = len(self.drones)
        
        if n_drones == 0:
            return {}
            
        positions = {}
        
        if formation_type == FormationType.LINE:
            spacing = kwargs.get("spacing", 2.0)
            for i, drone_id in enumerate(sorted(self.drones.keys())):
                offset = (i - n_drones / 2) * spacing
                positions[drone_id] = (
                    center[0] + offset,
                    center[1],
                    center[2]
                )
                
        elif formation_type == FormationType.GRID:
            cols = int(math.ceil(math.sqrt(n_drones)))
            spacing = kwargs.get("spacing", 3.0)
            idx = 0
            for row in range(int(math.ceil(n_drones / cols))):
                for col in range(cols):
                    if idx >= n_drones:
                        break
                    drone_id = sorted(self.drones.keys())[idx]
                    positions[drone_id] = (
                        center[0] + (col - cols / 2) * spacing,
                        center[1] + (row - math.ceil(n_drones / cols) / 2) * spacing,
                        center[2]
                    )
                    idx += 1
                    
        elif formation_type == FormationType.CIRCLE:
            radius = kwargs.get("radius", 10.0)
            for i, drone_id in enumerate(sorted(self.drones.keys())):
                angle = 2 * math.pi * i / n_drones
                positions[drone_id] = (
                    center[0] + radius * math.cos(angle),
                    center[1] + radius * math.sin(angle),
                    center[2]
                )
                
        elif formation_type == FormationType.STAR:
            # 5-pointed star pattern
            points_per_arm = n_drones // 5
            for i, drone_id in enumerate(sorted(self.drones.keys())):
                arm = i // points_per_arm
                pos_in_arm = i % points_per_arm
                
                # Spiral out from center
                r = radius * (pos_in_arm + 1) / points_per_arm
                angle = arm * 72 + pos_in_arm * 30
                
                positions[drone_id] = (
                    center[0] + r * math.cos(math.radians(angle)),
                    center[1] + r * math.sin(math.radians(angle)),
                    center[2]
                )
                
        else:
            # Default to grid
            spacing = kwargs.get("spacing", 3.0)
            cols = int(math.ceil(math.sqrt(n_drones)))
            idx = 0
            for row in range(int(math.ceil(n_drones / cols))):
                for col in range(cols):
                    if idx >= n_drones:
                        break
                    drone_id = sorted(self.drones.keys())[idx]
                    positions[drone_id] = (
                        center[0] + col * spacing,
                        center[1] + row * spacing,
                        center[2]
                    )
                    idx += 1
                    
        return positions
        
    def set_formation(
        self,
        formation_type: FormationType,
        center: Tuple[float, float, float] = (0, 0, 20),
        transition_time: float = 5.0,
        **kwargs
    ) -> bool:
        """
        Set new formation with smooth transition
        
        Args:
            formation_type: Type of formation
            center: Formation center
            transition_time: Time to transition (seconds)
            **kwargs: Additional formation parameters
        """
        target_positions = self.generate_formation(
            formation_type, center, **kwargs
        )
        
        if not target_positions:
            return False
            
        # Update target positions for all drones
        for drone_id, target in target_positions.items():
            if drone_id in self.drones:
                self.drones[drone_id].target_position = target
                
        logging.info(f"Formation set: {formation_type.value} with {len(target_positions)} drones")
        return True
        
    def update_targets(self, dt: float) -> Dict[int, Tuple[float, float, float]]:
        """
        Update drone targets based on current sequence
        
        Args:
            dt: Time since last update
            
        Returns:
            Dict of drone_id -> velocity command
        """
        commands = {}
        
        for drone_id, drone in self.drones.items():
            current = drone.position
            target = drone.target_position
            
            # Simple proportional control
            dx = target[0] - current[0]
            dy = target[1] - current[1]
            dz = target[2] - current[2]
            
            # Calculate velocity command
            speed = 2.0  # m/s max
            dist = math.sqrt(dx**2 + dy**2 + dz**2)
            
            if dist > 0.1:
                vx = dx / dist * min(speed, dist)
                vy = dy / dist * min(speed, dist)
                vz = dz / dist * min(speed, dist)
            else:
                vx = vy = vz = 0.0
                
            commands[drone_id] = (vx, vy, vz)
            
            # Update position (simulation)
            drone.position = (
                current[0] + vx * dt,
                current[1] + vy * dt,
                current[2] + vz * dt
            )
            
        return commands
        
    def check_sync(self) -> Tuple[bool, List[int]]:
        """
        Check if all drones are synchronized
        
        Returns:
            (is_synced, list_of_desynced_drone_ids)
        """
        desynced = []
        
        for drone_id, drone in self.drones.items():
            current = drone.position
            target = drone.target_position
            
            dist = math.sqrt(
                (current[0] - target[0])**2 +
                (current[1] - target[1])**2 +
                (current[2] - target[2])**2
            )
            
            if dist > self.position_tolerance:
                desynced.append(drone_id)
                
        return len(desynced) == 0, desynced
        
    def emergency_land_all(self, height: float = 2.0):
        """Emergency land all drones"""
        for drone_id, drone in self.drones.items():
            # Set target to 2m above current position
            drone.target_position = (
                drone.position[0],
                drone.position[1],
                drone.position[2] + height
            )
            drone.status = "emergency_landing"
            
        logging.warning("Emergency landing initiated for all drones")
        
    def hold_position_all(self):
        """All drones hold current position"""
        for drone_id, drone in self.drones.items():
            drone.target_position = drone.position
            drone.status = "holding"
            
        logging.info("All drones holding position")
        
    def set_led_pattern(
        self,
        drone_id: int,
        pattern: str,
        color: Tuple[int, int, int] = (255, 255, 255),
        speed: float = 1.0
    ):
        """Set LED pattern for drone"""
        if drone_id in self.drones:
            self.drones[drone_id].led_color = color
            # Pattern will be rendered at animation time
            
    def set_fleet_led(
        self,
        color: Tuple[int, int, int],
        pattern: str = "solid"
    ):
        """Set LED color/pattern for entire fleet"""
        for drone_id in self.drones:
            self.set_led_pattern(drone_id, pattern, color)
            
    def get_fleet_status(self) -> Dict[str, Any]:
        """Get status of entire fleet"""
        return {
            "total_drones": len(self.drones),
            "leader": self.leader_id,
            "drones": {
                drone_id: {
                    "position": drone.position,
                    "target": drone.target_position,
                    "battery": drone.battery,
                    "status": drone.status
                }
                for drone_id, drone in self.drones.items()
            }
        }


class DroneShowSequencer:
    """
    Sequence and timing for drone show choreography
    """
    
    def __init__(self, fleet: FleetManager):
        self.fleet = fleet
        self.sequences: List[ShowSequence] = []
        self.current_idx = 0
        
    def load_sequence(self, sequence: ShowSequence):
        """Load show sequence"""
        self.sequences.append(sequence)
        logging.info(f"Loaded sequence: {sequence.name}")
        
    def step_sequence(self, current_time: float):
        """
        Step through sequence based on time
        
        Args:
            current_time: Current show time (seconds from start)
        """
        if not self.sequences or self.current_idx >= len(self.sequences):
            return
            
        sequence = self.sequences[self.current_idx]
        
        # Calculate which formation to use
        formation_duration = sequence.duration / len(sequence.formations)
        formation_idx = int(current_time / formation_duration) % len(sequence.formations)
        
        # Apply formation
        formation = sequence.formations[formation_idx]
        for formation_name, points in formation.items():
            for point in points:
                self.fleet.drones[point.drone_id].target_position = point.position
                
    def start_show(self):
        """Start drone show"""
        self.fleet.sequence_start_time = time.time()
        self.current_idx = 0
        logging.info("Drone show started")
        
    def stop_show(self):
        """Stop drone show"""
        self.fleet.hold_position_all()
        logging.info("Drone show stopped")
        

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create fleet manager
    fleet = FleetManager(max_drones=20)
    
    # Add drones
    for i in range(10):
        fleet.add_drone(i + 1)
        
    # Set leader
    fleet.set_leader(1)
    
    # Set initial formation
    fleet.set_formation(FormationType.CIRCLE, center=(0, 0, 20), radius=8)
    
    print("Initial formation set")
    
    # Simulate updates
    for step in range(50):
        commands = fleet.update_targets(0.1)
        
        # Check sync
        synced, desynced = fleet.check_sync()
        if not synced:
            print(f"Step {step}: {len(desynced)} drones desynced")
            
        time.sleep(0.05)
        
    # Change formation
    print("\nChanging to star formation...")
    fleet.set_formation(FormationType.STAR, center=(0, 0, 25), radius=10)
    
    # Run sequence
    sequencer = DroneShowSequencer(fleet)
    sequencer.start_show()
    
    # Simulate show
    for t in range(100):
        sequencer.step_sequence(t * 0.5)
        fleet.update_targets(0.1)
        time.sleep(0.1)
        
    # Emergency test
    print("\nTesting emergency land...")
    fleet.emergency_land_all(height=3)
    
    # Get status
    status = fleet.get_fleet_status()
    print(f"Fleet status: {status['total_drones']} drones")