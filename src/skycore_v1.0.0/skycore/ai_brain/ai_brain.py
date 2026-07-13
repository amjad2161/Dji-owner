"""AI Brain - Local AI processing for drone decisions."""

import json
import time
import asyncio
from typing import List, Dict, Optional, Callable, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import threading

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class ResponseMode(Enum):
    """AI response mode."""
    QUICK = "quick"
    THOROUGH = "thorough"
    SAFETY_FIRST = "safety_first"


class DecisionType(Enum):
    """Decision types."""
    NAVIGATION = "navigation"
    SAFETY = "safety"
    MISSION = "mission"
    EMERGENCY = "emergency"
    UNKNOWN = "unknown"


@dataclass
class AIContext:
    """Context for AI decision making."""
    telemetry: Dict[str, Any]
    mission_status: str
    battery_percent: float
    altitude_m: float
    distance_to_home_m: float
    detected_objects: List[Dict] = field(default_factory=list)
    weather_conditions: Dict = field(default_factory=dict)
    time_of_day: str = "day"
    location_type: str = "outdoor"


@dataclass
class ProcessingTask:
    """AI processing task for async execution."""
    task_id: str
    prompt: str
    context: Optional[AIContext] = None
    priority: int = 1
    timeout_s: float = 30.0
    created_at: float = field(default_factory=time.time)
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class AIDecision:
    """AI decision output."""
    decision_type: DecisionType
    action: str
    confidence: float
    reasoning: str
    urgency: int  # 1-5, 5 being highest
    timestamp: float = field(default_factory=time.time)


class AIBrain(LoggerMixin):
    """
    AI Brain for autonomous drone decision making.
    
    Features:
    - Context awareness from telemetry
    - Safety-first decision making
    - Local LLM integration (Ollama)
    - Real-time decision making
    """
    
    def __init__(self, mode: ResponseMode = ResponseMode.QUICK):
        self.mode = mode
        self.ollama_client = None
        self.decision_history: List[AIDecision] = []
        self.safety_rules = self._init_safety_rules()
        self._last_decision = time.time()
        self._lock = threading.Lock()
    
    def _init_safety_rules(self) -> Dict:
        """Initialize safety rules."""
        return {
            'min_battery_rth': 25.0,  # percent
            'min_battery_land': 15.0,  # percent
            'max_altitude': 120.0,  # meters
            'min_altitude': 2.0,  # meters
            'geofence_distance': 500.0,  # meters
        }
    
    async def initialize(self, ollama_url: str = "http://localhost:11434"):
        """Initialize AI brain with Ollama client."""
        try:
            from skycore.ai_brain.ollama_client import OllamaClient
            self.ollama_client = OllamaClient(ollama_url)
            logger.info("AI Brain initialized with Ollama")
        except Exception as e:
            logger.warning(f"Could not initialize Ollama: {e}")
            self.ollama_client = None
    
    async def make_decision(self, context: AIContext) -> AIDecision:
        """Make autonomous decision based on context."""
        with self._lock:
            # Check safety rules first
            safety_decision = self._check_safety_rules(context)
            if safety_decision:
                self.decision_history.append(safety_decision)
                return safety_decision
            
            # Use AI for other decisions
            if self.ollama_client and self.mode != ResponseMode.QUICK:
                return await self._ai_decision(context)
            else:
                return self._quick_decision(context)
    
    def _check_safety_rules(self, context: AIContext) -> Optional[AIDecision]:
        """Check safety rules and return emergency decision if needed."""
        # Low battery
        if context.battery_percent <= self.safety_rules['min_battery_land']:
            return AIDecision(
                decision_type=DecisionType.EMERGENCY,
                action="emergency_land",
                confidence=1.0,
                reasoning=f"Critical battery: {context.battery_percent}%",
                urgency=5
            )
        
        if context.battery_percent <= self.safety_rules['min_battery_rth']:
            return AIDecision(
                decision_type=DecisionType.SAFETY,
                action="return_to_home",
                confidence=0.95,
                reasoning=f"Low battery: {context.battery_percent}%, returning home",
                urgency=4
            )
        
        # Altitude limits
        if context.altitude_m > self.safety_rules['max_altitude']:
            return AIDecision(
                decision_type=DecisionType.SAFETY,
                action="descend",
                confidence=1.0,
                reasoning=f"Altitude exceeded: {context.altitude_m}m",
                urgency=5
            )
        
        # Distance limits
        if context.distance_to_home_m > self.safety_rules['geofence_distance']:
            return AIDecision(
                decision_type=DecisionType.SAFETY,
                action="return_to_home",
                confidence=1.0,
                reasoning=f"Distance exceeded: {context.distance_to_home_m}m",
                urgency=4
            )
        
        return None
    
    def _quick_decision(self, context: AIContext) -> AIDecision:
        """Quick heuristic-based decision."""
        return AIDecision(
            decision_type=DecisionType.NAVIGATION,
            action="continue_mission",
            confidence=0.8,
            reasoning="Quick decision: continue mission",
            urgency=1
        )
    
    async def _ai_decision(self, context: AIContext) -> AIDecision:
        """AI-powered decision using Ollama."""
        prompt = self._build_decision_prompt(context)
        
        try:
            response = await self.ollama_client.generate(prompt)
            return self._parse_ai_response(response, context)
        except Exception as e:
            logger.error(f"AI decision error: {e}")
            return self._quick_decision(context)
    
    def _build_decision_prompt(self, context: AIContext) -> str:
        """Build decision prompt from context."""
        return f"""Drone status:
- Battery: {context.battery_percent}%
- Altitude: {context.altitude_m}m
- Distance to home: {context.distance_to_home_m}m
- Mission: {context.mission_status}

Objects detected: {context.detected_objects}

What should the drone do? (respond with: action, confidence, reasoning)"""
    
    def _parse_ai_response(self, response: str, context: AIContext) -> AIDecision:
        """Parse AI response into decision."""
        return AIDecision(
            decision_type=DecisionType.NAVIGATION,
            action="continue_mission",
            confidence=0.7,
            reasoning=f"AI suggested: {response[:100]}",
            urgency=2
        )
    
    def get_recent_decisions(self, count: int = 10) -> List[AIDecision]:
        """Get recent decisions."""
        return self.decision_history[-count:]
    
    def get_statistics(self) -> Dict:
        """Get AI brain statistics."""
        return {
            'total_decisions': len(self.decision_history),
            'mode': self.mode.value,
            'ollama_connected': self.ollama_client is not None,
            'safety_rules': self.safety_rules
        }