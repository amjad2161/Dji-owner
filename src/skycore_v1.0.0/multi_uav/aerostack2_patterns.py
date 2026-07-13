"""
SkyCore Aerostack2 Multi-UAV Integration
Based on Aerostack2 multi-robot architecture patterns

Features:
- Multi-agent mission execution
- Behavior-based control
- Shared world representation
- Inter-agent communication
- Mission coordination
"""

import time
import json
import logging
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import numpy as np


class MissionState(Enum):
    """Mission execution state"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"


@dataclass
class UAVAgent:
    """UAV agent in the swarm"""
    id: int
    name: str
    role: str  # leader, follower, scout
    capabilities: List[str] = field(default_factory=list)
    position: Tuple[float, float, float] = (0, 0, 0)
    battery_level: float = 100.0
    sensor_status: Dict[str, bool] = field(default_factory=dict)
    state: str = "idle"


@dataclass
class MissionTask:
    """Individual mission task"""
    task_id: str
    type: str  # survey, inspection, delivery, surveillance
    assigned_uav: Optional[int] = None
    waypoints: List[Tuple[float, float, float]] = field(default_factory=list)
    priority: int = 0
    estimated_duration: float = 0.0
    constraints: Dict[str, Any] = field(default_factory=dict)
    status: MissionState = MissionState.PENDING


@dataclass
class MultiUAVMission:
    """Complete multi-UAV mission"""
    mission_id: str
    name: str
    tasks: List[MissionTask] = field(default_factory=list)
    formation: str = "line"  # line, grid, circle, custom
    coordination_mode: str = "centralized"  # centralized, decentralized
    state: MissionState = MissionState.PENDING
    start_time: float = 0.0
    

class BehaviorBasedController:
    """
    Behavior-based control for UAV (Aerostack2 pattern)
    Combines behaviors to produce complex actions
    """
    
    def __init__(self, uav_id: int):
        self.uav_id = uav_id
        self.behaviors: Dict[str, Callable] = {}
        self.active_behaviors: List[str] = []
        self.behavior_outputs: Dict[str, Any] = {}
        
    def register_behavior(
        self,
        name: str,
        behavior_func: Callable,
        priority: int = 50
    ):
        """Register a behavior with priority (0-100)"""
        self.behaviors[name] = {
            "func": behavior_func,
            "priority": priority,
            "active": False
        }
        
    def activate_behavior(self, name: str):
        """Activate a behavior"""
        if name in self.behaviors:
            self.behaviors[name]["active"] = True
            if name not in self.active_behaviors:
                self.active_behaviors.append(name)
                
    def deactivate_behavior(self, name: str):
        """Deactivate a behavior"""
        if name in self.behaviors:
            self.behaviors[name]["active"] = False
            if name in self.active_behaviors:
                self.active_behaviors.remove(name)
                
    def update(self, perception_data: Dict) -> Dict[str, Any]:
        """
        Update all active behaviors and compute final action
        
        Args:
            perception_data: Sensor data and world state
            
        Returns:
            Final control action combining all behaviors
        """
        self.behavior_outputs = {}
        
        # Execute all active behaviors
        for name in self.active_behaviors:
            behavior = self.behaviors[name]
            try:
                output = behavior["func"](perception_data, self.uav_id)
                self.behavior_outputs[name] = output
            except Exception as e:
                logging.error(f"Behavior {name} error: {e}")
                
        # Combine behaviors using priority-weighted fusion
        final_action = self._fuse_behaviors()
        
        return final_action
        
    def _fuse_behaviors(self) -> Dict[str, Any]:
        """Fuse multiple behavior outputs based on priority"""
        if not self.behavior_outputs:
            return {"velocity": (0, 0, 0), "yaw_rate": 0, "altitude_change": 0}
            
        total_weight = 0
        fused_velocity = np.array([0.0, 0.0, 0.0])
        fused_yaw = 0.0
        fused_alt = 0.0
        
        for name, output in self.behavior_outputs.items():
            priority = self.behaviors[name]["priority"]
            weight = priority / 100.0
            
            if "velocity" in output:
                fused_velocity += np.array(output["velocity"]) * weight
            if "yaw_rate" in output:
                fused_yaw += output["yaw_rate"] * weight
            if "altitude_change" in output:
                fused_alt += output["altitude_change"] * weight
                
            total_weight += weight
            
        if total_weight > 0:
            fused_velocity /= total_weight
            fused_yaw /= total_weight
            fused_alt /= total_weight
            
        return {
            "velocity": tuple(fused_velocity),
            "yaw_rate": fused_yaw,
            "altitude_change": fused_alt
        }


class AerostackMissionExecutor:
    """
    Aerostack2-style multi-UAV mission executor
    Handles mission planning, allocation, and execution
    """
    
    def __init__(self):
        self.agents: Dict[int, UAVAgent] = {}
        self.missions: Dict[str, MultiUAVMission] = {}
        self.controllers: Dict[int, BehaviorBasedController] = {}
        self.world_state: Dict[str, Any] = {
            "obstacles": [],
            "no_fly_zones": [],
            "weather": {},
            "time": time.time()
        }
        
    def register_uav(self, uav: UAVAgent):
        """Register a UAV agent"""
        self.agents[uav.id] = uav
        self.controllers[uav.id] = BehaviorBasedController(uav.id)
        
        # Register default behaviors
        self._register_default_behaviors(uav.id)
        
        logging.info(f"Registered UAV {uav.id} as {uav.role}")
        
    def _register_default_behaviors(self, uav_id: int):
        """Register default Aerostack2 behaviors"""
        controller = self.controllers[uav_id]
        
        # Collision avoidance behavior
        def avoid_obstacles(perception, uid):
            obstacles = perception.get("obstacles", [])
            velocity = [0.0, 0.0, 0.0]
            
            for obs in obstacles:
                obs_pos = np.array(obs.get("position", [0, 0, 0]))
                uav_pos = np.array(perception.get("position", [0, 0, 0]))
                
                direction = uav_pos - obs_pos
                distance = np.linalg.norm(direction)
                
                if distance < 5.0:  # 5m safety radius
                    avoidance = direction / (distance + 0.1) * (5.0 - distance) / 5.0
                    velocity += avoidance
                    
            return {"velocity": tuple(np.clip(velocity, -1, 1)), "yaw_rate": 0, "altitude_change": 0}
            
        controller.register_behavior("obstacle_avoidance", avoid_obstacles, priority=90)
        
        # Goal seeking behavior
        def seek_goal(perception, uid):
            goal = perception.get("current_goal")
            if goal is None:
                return {"velocity": (0, 0, 0), "yaw_rate": 0, "altitude_change": 0}
                
            uav_pos = np.array(perception.get("position", [0, 0, 0]))
            goal_pos = np.array(goal)
            
            direction = goal_pos - uav_pos
            distance = np.linalg.norm(direction)
            
            if distance < 0.5:  # Reached goal
                return {"velocity": (0, 0, 0), "yaw_rate": 0, "altitude_change": 0}
                
            # Move towards goal at fixed speed
            velocity = direction / distance * 2.0  # 2 m/s
            
            return {"velocity": tuple(velocity), "yaw_rate": 0, "altitude_change": 0}
            
        controller.register_behavior("goal_seeking", seek_goal, priority=50)
        
        # Battery monitoring behavior
        def monitor_battery(perception, uid):
            battery = perception.get("battery_level", 100)
            
            if battery < 20:
                return {"velocity": (0, 0, 0), "yaw_rate": 0, "altitude_change": -1}
            elif battery < 30:
                return {"velocity": (0, 0, 0), "yaw_rate": 0, "altitude_change": -0.5}
                
            return {"velocity": (0, 0, 0), "yaw_rate": 0, "altitude_change": 0}
            
        controller.register_behavior("battery_management", monitor_battery, priority=80)
        
    def create_mission(
        self,
        mission_id: str,
        name: str,
        tasks: List[MissionTask],
        formation: str = "line",
        coordination: str = "centralized"
    ) -> MultiUAVMission:
        """Create a multi-UAV mission"""
        mission = MultiUAVMission(
            mission_id=mission_id,
            name=name,
            tasks=tasks,
            formation=formation,
            coordination_mode=coordination
        )
        
        self.missions[mission_id] = mission
        return mission
        
    def allocate_tasks(self, mission_id: str) -> bool:
        """
        Allocate mission tasks to available UAVs
        
        Returns:
            True if allocation successful
        """
        if mission_id not in self.missions:
            return False
            
        mission = self.missions[mission_id]
        
        # Sort tasks by priority
        sorted_tasks = sorted(mission.tasks, key=lambda t: t.priority, reverse=True)
        
        for task in sorted_tasks:
            # Find best UAV for task
            best_uav = self._find_best_uav(task)
            
            if best_uav is not None:
                task.assigned_uav = best_uav.id
                logging.info(f"Task {task.task_id} allocated to UAV {best_uav.id}")
            else:
                logging.warning(f"No suitable UAV for task {task.task_id}")
                
        return True
        
    def _find_best_uav(self, task: MissionTask) -> Optional[UAVAgent]:
        """Find best UAV for a task based on capabilities and availability"""
        suitable_uavs = []
        
        for uav_id, uav in self.agents.items():
            # Check if UAV is available
            if uav.state != "idle":
                continue
                
            # Check if UAV has required capabilities
            required_caps = task.constraints.get("required_capabilities", [])
            if required_caps and not all(cap in uav.capabilities for cap in required_caps):
                continue
                
            # Check battery
            min_battery = task.constraints.get("min_battery", 20)
            if uav.battery_level < min_battery:
                continue
                
            suitable_uavs.append(uav)
            
        if not suitable_uavs:
            return None
            
        # Return UAV with highest battery (simple heuristic)
        return max(suitable_uavs, key=lambda u: u.battery_level)
        
    def execute_mission(self, mission_id: str) -> bool:
        """Start mission execution"""
        if mission_id not in self.missions:
            return False
            
        mission = self.missions[mission_id]
        mission.state = MissionState.RUNNING
        mission.start_time = time.time()
        
        # Activate behaviors for all assigned UAVs
        for task in mission.tasks:
            if task.assigned_uav is not None:
                controller = self.controllers[task.assigned_uav]
                controller.activate_behavior("goal_seeking")
                controller.activate_behavior("obstacle_avoidance")
                controller.activate_behavior("battery_management")
                
                # Update agent state
                self.agents[task.assigned_uav].state = "executing"
                
        logging.info(f"Mission {mission_id} started")
        return True
        
    def update_mission(self, mission_id: str) -> MissionState:
        """Update mission execution state"""
        if mission_id not in self.missions:
            return MissionState.ABORTED
            
        mission = self.missions[mission_id]
        
        # Check all tasks
        all_completed = True
        any_aborted = False
        
        for task in mission.tasks:
            if task.assigned_uav is None:
                continue
                
            uav = self.agents[task.assigned_uav]
            
            # Check if task waypoints reached
            if task.status == MissionState.RUNNING:
                # Simulate progress
                if len(task.waypoints) > 0:
                    remaining = len(task.waypoints)
                    # For demo, complete after some time
                    if uav.state == "executing":
                        pass  # Continue execution
                        
                # Check if UAV reached all waypoints
                if remaining == 0:
                    task.status = MissionState.COMPLETED
                    uav.state = "idle"
                    
        # Update mission state
        for task in mission.tasks:
            if task.status == MissionState.RUNNING:
                all_completed = False
            elif task.status == MissionState.ABORTED:
                any_aborted = True
                
        if any_aborted:
            mission.state = MissionState.ABORTED
        elif all_completed:
            mission.state = MissionState.COMPLETED
            
        return mission.state
        
    def get_mission_status(self, mission_id: str) -> Dict[str, Any]:
        """Get detailed mission status"""
        if mission_id not in self.missions:
            return {"error": "Mission not found"}
            
        mission = self.missions[mission_id]
        
        task_summary = []
        for task in mission.tasks:
            task_summary.append({
                "task_id": task.task_id,
                "type": task.type,
                "assigned_uav": task.assigned_uav,
                "status": task.status.value
            })
            
        return {
            "mission_id": mission_id,
            "name": mission.name,
            "state": mission.state.value,
            "elapsed_time": time.time() - mission.start_time if mission.start_time > 0 else 0,
            "tasks": task_summary
        }


class SharedWorldRepresentation:
    """
    Aerostack2 shared world representation
    Maintains consistent state across all UAVs
    """
    
    def __init__(self):
        self.observations: List[Dict] = []
        self.occupancy_grid: Optional[np.ndarray] = None
        self.known_areas: Dict[str, float] = {}  # area_id -> coverage %
        
    def add_observation(self, observation: Dict):
        """Add observation from any UAV"""
        observation["timestamp"] = time.time()
        self.observations.append(observation)
        
    def update_occupancy_grid(
        self,
        grid: np.ndarray,
        resolution: float = 0.1
    ):
        """Update occupancy grid from observations"""
        self.occupancy_grid = grid
        
    def get_coverage(self, area_id: str) -> float:
        """Get coverage percentage for area"""
        return self.known_areas.get(area_id, 0.0)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create executor
    executor = AerostackMissionExecutor()
    
    # Register UAVs
    executor.register_uav(UAVAgent(
        id=1,
        name="UAV-1",
        role="leader",
        capabilities=["survey", "inspection", "delivery"]
    ))
    
    executor.register_uav(UAVAgent(
        id=2,
        name="UAV-2",
        role="follower",
        capabilities=["survey", "inspection"]
    ))
    
    executor.register_uav(UAVAgent(
        id=3,
        name="UAV-3",
        role="scout",
        capabilities=["surveillance", "delivery"]
    ))
    
    # Create mission
    tasks = [
        MissionTask(
            task_id="survey_1",
            type="survey",
            waypoints=[(32.08, 34.78, 30), (32.09, 34.79, 30)],
            priority=1,
            constraints={"min_battery": 40}
        ),
        MissionTask(
            task_id="inspect_1",
            type="inspection",
            waypoints=[(32.085, 34.785, 20), (32.086, 34.786, 20)],
            priority=2,
            constraints={"required_capabilities": ["inspection"]}
        )
    ]
    
    mission = executor.create_mission(
        "mission_001",
        "Area Survey",
        tasks,
        formation="grid"
    )
    
    # Allocate and execute
    executor.allocate_tasks("mission_001")
    executor.execute_mission("mission_001")
    
    # Simulate update
    status = executor.get_mission_status("mission_001")
    print(f"Mission state: {status['state']}")
    print(f"Tasks: {len(status['tasks'])}")
    
    # Test behavior controller
    controller = executor.controllers[1]
    perception = {
        "position": [32.08, 34.78, 30],
        "battery_level": 85,
        "obstacles": [{"position": [32.081, 34.781, 30]}],
        "current_goal": [32.09, 34.79, 30]
    }
    
    action = controller.update(perception)
    print(f"Control action: {action}")