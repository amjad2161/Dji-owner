"""
Mission Executor
Executes waypoint missions with state machine
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class MissionState(Enum):
    """Mission execution states."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"
    EMERGENCY = "emergency"


@dataclass
class MissionWaypoint:
    """Mission waypoint definition."""
    lat: float
    lon: float
    alt: float = 30.0
    speed_mps: float = 5.0
    heading_deg: float = 0.0
    gimbal_pitch: float = -90.0
    hover_time_s: float = 0.0
    action: Optional[str] = None  # photo, video, etc.


@dataclass
class MissionStatus:
    """Mission execution status."""
    state: MissionState
    current_waypoint: int = 0
    total_waypoints: int = 0
    progress_pct: float = 0.0
    distance_remaining_m: float = 0.0
    eta_seconds: float = 0.0
    battery_remaining_pct: float = 100.0


class MissionExecutor:
    """
    Mission execution controller.
    
    Features:
    - Waypoint mission execution
    - State machine control
    - Progress tracking
    - Emergency handling
    - Pause/resume capability
    """
    
    def __init__(self, drone=None):
        self.drone = drone
        self.mission_waypoints: List[MissionWaypoint] = []
        self.state = MissionState.IDLE
        self.current_waypoint = 0
        
        # Callbacks
        self._waypoint_callbacks: List[Callable] = []
        self._state_callbacks: List[Callable] = []
        
        # Statistics
        self.mission_start_time = 0.0
        self.waypoints_completed = 0
        self.total_distance_m = 0.0
        
        # Control
        self._running = False
        self._paused = False
        self._task: Optional[asyncio.Task] = None
        
        logger.info("Mission executor initialized")
    
    def load_mission(self, waypoints: List[MissionWaypoint]) -> bool:
        """Load mission waypoints."""
        if not waypoints:
            logger.warning("Empty mission waypoints")
            return False
        
        self.mission_waypoints = waypoints
        self.current_waypoint = 0
        self.state = MissionState.PLANNING
        self.total_distance_m = self._calculate_total_distance()
        
        logger.info(f"Mission loaded: {len(waypoints)} waypoints, {self.total_distance_m:.0f}m total")
        return True
    
    def load_from_litchi_csv(self, csv_path: str) -> bool:
        """Load mission from Litchi CSV file."""
        try:
            from skycore.missions.litchi import LitchiMission
            
            mission = LitchiMission.from_csv(csv_path)
            
            waypoints = []
            for wp in mission.waypoints:
                waypoints.append(MissionWaypoint(
                    lat=wp.latitude,
                    lon=wp.longitude,
                    alt=wp.altitude,
                    speed_mps=wp.speed if wp.speed > 0 else 5.0,
                    heading_deg=wp.heading,
                    gimbal_pitch=wp.gimbal_pitch,
                    hover_time_s=wp.hover_time
                ))
            
            return self.load_mission(waypoints)
            
        except Exception as e:
            logger.error(f"Failed to load Litchi CSV: {e}")
            return False
    
    async def start(self) -> bool:
        """Start mission execution."""
        if not self.mission_waypoints:
            logger.error("No mission loaded")
            return False
        
        if self.state == MissionState.EXECUTING:
            logger.warning("Mission already executing")
            return False
        
        self.state = MissionState.EXECUTING
        self.mission_start_time = time.time()
        self._running = True
        self._paused = False
        
        logger.info("Mission started")
        
        # Start execution task
        self._task = asyncio.create_task(self._execute_loop())
        
        return True
    
    async def pause(self):
        """Pause mission execution."""
        if self.state == MissionState.EXECUTING:
            self._paused = True
            self.state = MissionState.PAUSED
            logger.info("Mission paused")
    
    async def resume(self):
        """Resume paused mission."""
        if self.state == MissionState.PAUSED:
            self._paused = False
            self.state = MissionState.EXECUTING
            logger.info("Mission resumed")
    
    async def abort(self):
        """Abort mission execution."""
        self._running = False
        self.state = MissionState.ABORTED
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.warning("Mission aborted")
    
    async def _execute_loop(self):
        """Main mission execution loop."""
        try:
            while self._running and self.current_waypoint < len(self.mission_waypoints):
                if self._paused:
                    await asyncio.sleep(0.1)
                    continue
                
                # Get current waypoint
                wp = self.mission_waypoints[self.current_waypoint]
                
                # Execute waypoint
                await self._execute_waypoint(wp)
                
                # Move to next
                self.current_waypoint += 1
                self.waypoints_completed += 1
                
                # Notify callbacks
                for callback in self._waypoint_callbacks:
                    try:
                        await callback(self.current_waypoint, wp)
                    except Exception as e:
                        logger.error(f"Waypoint callback error: {e}")
            
            # Mission complete
            if self.current_waypoint >= len(self.mission_waypoints):
                self.state = MissionState.COMPLETED
                logger.info("Mission completed")
            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Mission execution error: {e}")
            self.state = MissionState.ABORTED
    
    async def _execute_waypoint(self, waypoint: MissionWaypoint):
        """Execute a single waypoint."""
        if self.drone is None:
            logger.warning("No drone connected, simulating waypoint")
            await asyncio.sleep(1.0)
            return
        
        try:
            from skycore.core.types import GeoPoint
            
            # Go to waypoint
            target = GeoPoint(waypoint.lat, waypoint.lon, waypoint.alt)
            await self.drone.goto(target, waypoint.speed_mps)
            
            # Hover if needed
            if waypoint.hover_time_s > 0:
                await asyncio.sleep(waypoint.hover_time_s)
            
            # Execute action if any
            if waypoint.action == "photo":
                await self.drone.take_photo()
            elif waypoint.action == "video":
                await self.drone.start_recording()
            
        except Exception as e:
            logger.error(f"Waypoint execution error: {e}")
            raise
    
    def _calculate_total_distance(self) -> float:
        """Calculate total mission distance."""
        if len(self.mission_waypoints) < 2:
            return 0.0
        
        total = 0.0
        for i in range(1, len(self.mission_waypoints)):
            prev = self.mission_waypoints[i-1]
            curr = self.mission_waypoints[i]
            
            from skycore.core.types import GeoPoint
            p1 = GeoPoint(prev.lat, prev.lon, prev.alt)
            p2 = GeoPoint(curr.lat, curr.lon, curr.alt)
            
            dist = p1.haversine_m(p2)
            total += dist
        
        return total
    
    def get_status(self) -> MissionStatus:
        """Get current mission status."""
        progress = (self.current_waypoint / max(1, len(self.mission_waypoints))) * 100
        remaining = len(self.mission_waypoints) - self.current_waypoint
        
        return MissionStatus(
            state=self.state,
            current_waypoint=self.current_waypoint,
            total_waypoints=len(self.mission_waypoints),
            progress_pct=progress,
            distance_remaining_m=self._calculate_remaining_distance(),
            eta_seconds=remaining * 30.0,  # Estimate
            battery_remaining_pct=100.0
        )
    
    def _calculate_remaining_distance(self) -> float:
        """Calculate remaining distance."""
        if self.current_waypoint >= len(self.mission_waypoints):
            return 0.0
        
        total = 0.0
        for i in range(self.current_waypoint, len(self.mission_waypoints) - 1):
            curr = self.mission_waypoints[i]
            next_wp = self.mission_waypoints[i + 1]
            
            from skycore.core.types import GeoPoint
            p1 = GeoPoint(curr.lat, curr.lon, curr.alt)
            p2 = GeoPoint(next_wp.lat, next_wp.lon, next_wp.alt)
            
            total += p1.haversine_m(p2)
        
        return total
    
    def on_waypoint(self, callback: Callable):
        """Register waypoint callback."""
        self._waypoint_callbacks.append(callback)
    
    def on_state_change(self, callback: Callable):
        """Register state change callback."""
        self._state_callbacks.append(callback)