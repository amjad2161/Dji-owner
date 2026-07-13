"""OpenRouter AI API integration for intelligent drone assistance.

Implements:
- OpenRouter API client
- Mission planning assistance
- Anomaly detection and diagnosis
- Natural language command interpretation
- Reporting and analysis generation
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable
import time
import json
import urllib.request
import urllib.parse


@dataclass
class OpenRouterConfig:
    """OpenRouter API configuration."""
    api_key: Optional[str] = None
    base_url: str = "https://openrouter.ai/api/v1"
    
    # Model settings
    default_model: str = "anthropic/claude-3-haiku"
    max_tokens: int = 1024
    temperature: float = 0.7
    
    # Rate limiting
    request_interval: float = 1.0
    max_retries: int = 3
    
    # Cache
    cache_duration: float = 300.0


@dataclass
class AIResponse:
    """AI model response."""
    content: str
    model: str
    usage: Dict
    latency: float
    timestamp: float


class OpenRouterClient:
    """OpenRouter AI API client."""
    
    def __init__(self, config: Optional[OpenRouterConfig] = None):
        self.config = config or OpenRouterConfig()
        
        # Cache
        self._cache: Dict[str, Tuple[float, AIResponse]] = {}
        
        # Rate limiting
        self.last_request = 0
        
        # Session for conversation context
        self.conversation_history: List[Dict] = []
        self.max_history = 20
    
    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        use_cache: bool = True
    ) -> Optional[AIResponse]:
        """Send chat request to AI model.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            model: Model to use (default: config.default_model)
            use_cache: Whether to use cached response
            
        Returns:
            AIResponse or None
        """
        if use_cache:
            # Check cache
            cache_key = f"{model}_{prompt[:100]}"
            if cache_key in self._cache:
                cached_time, cached_response = self._cache[cache_key]
                if time.time() - cached_time < self.config.cache_duration:
                    return cached_response
        
        # Rate limiting
        elapsed = time.time() - self.last_request
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        
        # Build request
        headers = {
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json'
        }
        
        messages = []
        
        # System prompt
        if system_prompt:
            messages.append({
                'role': 'system',
                'content': system_prompt
            })
        
        # Add conversation history
        messages.extend(self.conversation_history)
        
        # Add current prompt
        messages.append({
            'role': 'user',
            'content': prompt
        })
        
        data = {
            'model': model or self.config.default_model,
            'messages': messages,
            'max_tokens': self.config.max_tokens,
            'temperature': self.config.temperature
        }
        
        start_time = time.time()
        
        try:
            req = urllib.request.Request(
                f"{self.config.base_url}/chat/completions",
                data=json.dumps(data).encode(),
                headers=headers
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
            
            # Parse response
            content = result['choices'][0]['message']['content']
            
            response_obj = AIResponse(
                content=content,
                model=result.get('model', model or self.config.default_model),
                usage=result.get('usage', {}),
                latency=time.time() - start_time,
                timestamp=time.time()
            )
            
            # Update history
            self.conversation_history.append({
                'role': 'user',
                'content': prompt
            })
            self.conversation_history.append({
                'role': 'assistant',
                'content': content
            })
            
            if len(self.conversation_history) > self.max_history * 2:
                self.conversation_history = self.conversation_history[-self.max_history * 2:]
            
            self.last_request = time.time()
            
            # Cache
            if use_cache:
                self._cache[cache_key] = (time.time(), response_obj)
            
            return response_obj
            
        except Exception as e:
            print(f"OpenRouter API error: {e}")
            return None
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
    
    def analyze_telemetry(
        self,
        telemetry_data: Dict
    ) -> Optional[str]:
        """Analyze telemetry data for anomalies.
        
        Args:
            telemetry_data: Telemetry dictionary
            
        Returns:
            Analysis result or None
        """
        system_prompt = """You are a drone flight analyst. Analyze the telemetry data provided
and identify any anomalies, safety concerns, or areas for improvement. Provide concise
analysis focusing on actionable insights."""
        
        prompt = f"Analyze this telemetry data:\n{json.dumps(telemetry_data, indent=2)}"
        
        response = self.chat(prompt, system_prompt)
        
        return response.content if response else None
    
    def suggest_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        constraints: Dict
    ) -> Optional[str]:
        """Suggest optimal route given constraints.
        
        Args:
            start: (lat, lon) start position
            end: (lat, lon) end position
            constraints: Route constraints (no-fly zones, weather, etc.)
            
        Returns:
            Route suggestion or None
        """
        system_prompt = """You are a drone navigation assistant. Based on the mission parameters
provided, suggest an optimal flight route. Consider weather, airspace restrictions,
battery efficiency, and safety margins. Provide route as waypoints or descriptive guidance."""
        
        prompt = f"""Plan route from {start} to {end}
        
Constraints:
{json.dumps(constraints, indent=2)}
        
Provide a safe and efficient route plan."""
        
        response = self.chat(prompt, system_prompt)
        
        return response.content if response else None
    
    def diagnose_issue(
        self,
        error_description: str,
        flight_log: Optional[str] = None
    ) -> Optional[str]:
        """Diagnose drone issue from error description.
        
        Args:
            error_description: Description of the problem
            flight_log: Optional flight log excerpt
            
        Returns:
            Diagnosis and recommendations or None
        """
        system_prompt = """You are a drone technical support specialist. Analyze the reported
issue and provide possible causes, diagnostic steps, and recommended solutions.
Be thorough but concise. Prioritize safety-critical issues."""
        
        prompt = f"""Diagnose this drone issue:

Error Description: {error_description}

{f'Flight Log:\n{flight_log}' if flight_log else ''}
"""
        
        response = self.chat(prompt, system_prompt)
        
        return response.content if response else None
    
    def generate_report(
        self,
        mission_data: Dict,
        telemetry_summary: Dict
    ) -> Optional[str]:
        """Generate mission report.
        
        Args:
            mission_data: Mission parameters and status
            telemetry_summary: Telemetry data summary
            
        Returns:
            Formatted report or None
        """
        system_prompt = """You are a drone mission analyst. Generate a comprehensive but
concise mission report. Include mission objectives, actual vs planned execution,
performance metrics, anomalies encountered, and recommendations for future missions."""
        
        prompt = f"""Generate mission report:

Mission Data:
{json.dumps(mission_data, indent=2)}

Telemetry Summary:
{json.dumps(telemetry_summary, indent=2)}
"""
        
        response = self.chat(prompt, system_prompt)
        
        return response.content if response else None
    
    def interpret_command(
        self,
        voice_command: str,
        context: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Interpret natural language command into structured drone command.
        
        Args:
            voice_command: Natural language command
            context: Current drone state context
            
        Returns:
            Structured command dictionary or None
        """
        system_prompt = """You are a drone command interpreter. Convert natural language
commands into structured drone commands. Output valid JSON with:
- command_type: (goto, land, rtl, takeoff, hover, circle, etc.)
- parameters: relevant parameters (lat, lon, alt, speed, radius, etc.)
- safety_checks: list of required safety checks
- confirmation_needed: boolean

Only output the JSON, no explanation."""
        
        context_str = f"\nCurrent state: {json.dumps(context)}" if context else ""
        prompt = f"Parse this command:{context_str}\n\nCommand: {voice_command}"
        
        response = self.chat(prompt, system_prompt)
        
        if response:
            try:
                # Extract JSON from response
                content = response.content.strip()
                
                # Handle markdown code blocks
                if content.startswith('```'):
                    lines = content.split('\n')
                    content = '\n'.join(lines[1:-1])
                
                return json.loads(content)
            except json.JSONDecodeError:
                return None
        
        return None


def demo_openrouter():
    """Demonstrate OpenRouter API integration."""
    print("=" * 60)
    print("OpenRouter AI API Demo")
    print("=" * 60)
    
    # Create client
    config = OpenRouterConfig()
    client = OpenRouterClient(config)
    
    print("\nNote: Add your OpenRouter API key for live AI capabilities")
    
    # Demonstrate command interpretation
    print("\n" + "=" * 40)
    print("Command Interpretation Demo")
    print("=" * 40)
    
    test_commands = [
        "fly to the field at 50 meters",
        "take me to the tower",
        "land here",
        "hover for a minute",
        "orbit around home at 30 meters"
    ]
    
    context = {
        'position': {'lat': 32.0853, 'lon': 34.7818, 'alt': 30},
        'battery': 0.75,
        'status': 'flying'
    }
    
    print(f"\nContext: {json.dumps(context, indent=2)}\n")
    
    for cmd in test_commands:
        print(f"Input: \"{cmd}\"")
        # In real implementation, would call interpret_command
        print("  (Add API key to test live interpretation)")
        print()


if __name__ == "__main__":
    demo_openrouter()