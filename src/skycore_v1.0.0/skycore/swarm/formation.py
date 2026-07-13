"""
Swarm Formation Controller
Maintains geometric formations for drone swarms
"""

import math
import asyncio
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

import logging

logger = logging.getLogger(__name__)


class FormationType(Enum):
    """Formation types."""
    LINE = "line"
    V_SHAPE = "v_shape"
    SQUARE = "square"
    CIRCLE = "circle"
    GRID = "grid"
    FOLLOW_LEADER = "follow_leader"


@dataclass
class FormationPoint:
    """Formation point for a single drone."""
    offset_x: float  # meters relative to formation center
    offset_y: float  # meters relative to formation center
    altitude: float = 0.0  # meters
    slot_index: int = 0


@dataclass
class DroneFormationState:
    """Current formation state of a drone."""
    drone_id: int
    target_x: float
    target_y: float
    target_alt: float
    position_x: float = 0.0
    position_y: float = 0.0
    in_position: bool = False


class FormationController:
    """
    Swarm formation controller.
    
    Features:
    - Multiple formation types
    - Dynamic formation switching
    - Collision avoidance within formation
    - Leader-follower coordination
    """
    
    def __init__(self, formation_type: FormationType = FormationType.LINE):
        self.formation_type = formation_type
        self.formation_points: List[FormationPoint] = []
        self.drone_states: Dict[int, DroneFormationState] = {}
        self.leader_id: Optional[int] = None
        self.formation_center_x: float = 0.0
        self.formation_center_y: float = 0.0
        self.formation_spacing: float = 3.0  # meters
        self.arrival_tolerance: float = 1.0  # meters
        self._compute_formation()
    
    def set_formation_type(self, formation_type: FormationType, drone_count: int):
        """Set formation type and recompute positions."""
        self.formation_type = formation_type
        self._compute_formation(drone_count)
        logger.info(f"Formation changed to {formation_type.value} with {drone_count} drones")
    
    def _compute_formation(self, drone_count: int = 4):
        """Compute formation points based on type."""
        self.formation_points = []
        
        if self.formation_type == FormationType.LINE:
            for i in range(drone_count):
                self.formation_points.append(FormationPoint(
                    offset_x=i * self.formation_spacing,
                    offset_y=0.0,
                    slot_index=i
                ))
        
        elif self.formation_type == FormationType.V_SHAPE:
            # V shape: leader + followers
            self.formation_points.append(FormationPoint(0, 0, slot_index=0))  # Leader
            for i in range(1, drone_count):
                side = 1 if i % 2 == 1 else -1
                row = (i + 1) // 2
                self.formation_points.append(FormationPoint(
                    offset_x=row * self.formation_spacing,
                    offset_y=side * row * self.formation_spacing * 0.5,
                    slot_index=i
                ))
        
        elif self.formation_type == FormationType.SQUARE:
            side = math.ceil(math.sqrt(drone_count))
            for i in range(drone_count):
                row = i // side
                col = i % side
                self.formation_points.append(FormationPoint(
                    offset_x=col * self.formation_spacing,
                    offset_y=row * self.formation_spacing,
                    slot_index=i
                ))
        
        elif self.formation_type == FormationType.CIRCLE:
            for i in range(drone_count):
                angle = 2 * math.pi * i / drone_count
                radius = self.formation_spacing * drone_count / (2 * math.pi)
                self.formation_points.append(FormationPoint(
                    offset_x=radius * math.cos(angle),
                    offset_y=radius * math.sin(angle),
                    slot_index=i
                ))
        
        else:
            # Default to grid
            cols = int(math.sqrt(drone_count)) + 1
            for i in range(drone_count):
                row = i // cols
                col = i % cols
                self.formation_points.append(FormationPoint(
                    offset_x=col * self.formation_spacing,
                    offset_y=row * self.formation_spacing,
                    slot_index=i
                ))
    
    def register_drone(self, drone_id: int, slot_index: int):
        """Register a drone with a formation slot."""
        if slot_index >= len(self.formation_points):
            # Expand formation
            self._compute_formation(max(slot_index + 1, len(self.formation_points) + 1))
        
        self.drone_states[drone_id] = DroneFormationState(
            drone_id=drone_id,
            target_x=self.formation_center_x + self.formation_points[slot_index].offset_x,
            target_y=self.formation_center_y + self.formation_points[slot_index].offset_y,
            target_alt=self.formation_points[slot_index].altitude
        )
        logger.info(f"Drone {drone_id} registered at slot {slot_index}")
    
    def unregister_drone(self, drone_id: int):
        """Unregister a drone from formation."""
        if drone_id in self.drone_states:
            del self.drone_states[drone_id]
            logger.info(f"Drone {drone_id} unregistered from formation")
    
    def set_leader(self, leader_id: int):
        """Set formation leader."""
        self.leader_id = leader_id
        if leader_id not in self.drone_states:
            self.register_drone(leader_id, 0)
        logger.info(f"Leader set to drone {leader_id}")
    
    def move_formation(self, center_x: float, center_y: float):
        """Move formation center to new position."""
        dx = center_x - self.formation_center_x
        dy = center_y - self.formation_center_y
        
        self.formation_center_x = center_x
        self.formation_center_y = center_y
        
        # Update all drone targets
        for drone_id, state in self.drone_states.items():
            if drone_id in self.drone_states:
                state.target_x += dx
                state.target_y += dy
    
    def update_drone_position(self, drone_id: int, x: float, y: float):
        """Update drone's current position."""
        if drone_id in self.drone_states:
            state = self.drone_states[drone_id]
            state.position_x = x
            state.position_y = y
            
            # Check if in position
            dist = math.sqrt((x - state.target_x)**2 + (y - state.target_y)**2)
            state.in_position = dist <= self.arrival_tolerance
    
    def get_target_position(self, drone_id: int) -> Optional[Tuple[float, float, float]]:
        """Get target position for a drone."""
        if drone_id not in self.drone_states:
            return None
        
        state = self.drone_states[drone_id]
        return (state.target_x, state.target_y, state.target_alt)
    
    def get_leader_position(self) -> Optional[Tuple[float, float, float]]:
        """Get leader's position if set."""
        if self.leader_id and self.leader_id in self.drone_states:
            state = self.drone_states[self.leader_id]
            return (state.position_x, state.position_y, state.target_alt)
        return None
    
    def all_in_position(self) -> bool:
        """Check if all drones are in position."""
        if not self.drone_states:
            return True
        return all(state.in_position for state in self.drone_states.values())
    
    def get_formation_positions(self) -> Dict[int, Tuple[float, float, float]]:
        """Get all formation target positions."""
        return {
            drone_id: (state.target_x, state.target_y, state.target_alt)
            for drone_id, state in self.drone_states.items()
        }
    
    def get_statistics(self) -> Dict:
        """Get formation statistics."""
        return {
            'formation_type': self.formation_type.value,
            'drone_count': len(self.drone_states),
            'leader_id': self.leader_id,
            'all_in_position': self.all_in_position(),
            'center': (self.formation_center_x, self.formation_center_y)
        }