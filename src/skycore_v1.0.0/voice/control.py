"""Voice command processing for drone control.

Implements:
- Speech recognition (offline/online)
- Command parsing and validation
- Natural language understanding
- Command confirmation workflow
- Safety checks
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable, Tuple
import re
import time
import numpy as np


@dataclass
class VoiceConfig:
    """Voice command configuration."""
    # Recognition settings
    model_type: str = "offline"  # "offline", "online"
    language: str = "en-US"
    
    # Command settings
    require_confirmation: bool = True
    confirmation_timeout: float = 5.0  # seconds
    
    # Safety
    enable_safety_checks: bool = True
    max_altitude_command: float = 120.0  # meters
    max_distance_command: float = 500.0   # meters from home
    
    # Keyword spotting
    wake_word: str = "skycore"
    keyword_threshold: float = 0.7


@dataclass
class Command:
    """Parsed voice command."""
    command_type: str       # "goto", "land", "rtl", etc.
    parameters: Dict         # Command-specific parameters
    raw_text: str           # Original transcribed text
    
    # Confidence
    confidence: float = 1.0
    
    # Status
    confirmed: bool = False
    executed: bool = False
    timestamp: float = 0.0
    error: Optional[str] = None


class CommandParser:
    """Parse and understand voice commands."""
    
    # Command patterns (regex-based)
    COMMAND_PATTERNS = {
        'goto': [
            r'go\s+to\s+(?P<location>\w+)',
            r'navigate\s+to\s+(?P<location>\w+)',
            r'fly\s+to\s+(?P<location>\w+)',
            r'move\s+to\s+(?P<location>\w+)',
        ],
        'land': [
            r'land',
            r'land\s+here',
            r'set\s+down',
            r'come\s+down',
        ],
        'rtl': [
            r'return\s+to\s+home',
            r'rtl',
            r'go\s+home',
            r'come\s+back',
            r'return',
        ],
        'takeoff': [
            r'take\s*off',
            r'launch',
            r'go\s+up',
            r'fly\s+up',
        ],
        'hover': [
            r'hover',
            r'hold\s+position',
            r'stay\s+here',
            r'pause',
            r'wait',
        ],
        'circle': [
            r'circle\s+(?P<location>\w+)',
            r'orbit\s+(?P<location>\w+)',
        ],
        'speed': [
            r'set\s+speed\s+to\s+(?P<speed>\w+)',
            r'speed\s+(?P<speed>\w+)',
            r'fly\s+(?P<speed>\w+)',
        ],
        'altitude': [
            r'set\s+altitude\s+to\s+(?P<alt>\d+)',
            r'alt\s+(?P<alt>\d+)',
            r'climb\s+to\s+(?P<alt>\d+)',
            r'descend\s+to\s+(?P<alt>\d+)',
        ],
        'emergency': [
            r'emergency\s+land',
            r'land\s+now',
            r'stop',
            r'stop\s+motors',
            r'shutdown',
        ],
    }
    
    # Location synonyms
    LOCATIONS = {
        'home': {'lat': 32.0853, 'lon': 34.7818, 'alt': 10},
        'start': {'lat': 32.0853, 'lon': 34.7818, 'alt': 10},
        'base': {'lat': 32.0853, 'lon': 34.7818, 'alt': 10},
        'park': {'lat': 32.0825, 'lon': 34.7890, 'alt': 20},
        'field': {'lat': 32.0780, 'lon': 34.7950, 'alt': 30},
    }
    
    # Speed mappings
    SPEEDS = {
        'slow': 2.0,
        'medium': 5.0,
        'fast': 10.0,
        'very fast': 15.0,
    }
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        
        # Compile patterns
        self.patterns = {}
        for cmd_type, patterns in self.COMMAND_PATTERNS.items():
            self.patterns[cmd_type] = [re.compile(p, re.IGNORECASE) for p in patterns]
    
    def parse(self, text: str) -> Optional[Command]:
        """Parse voice command text.
        
        Args:
            text: Transcribed text
            
        Returns:
            Command object or None if unparseable
        """
        text = text.strip()
        
        for cmd_type, patterns in self.patterns.items():
            for pattern in patterns:
                match = pattern.search(text)
                
                if match:
                    params = match.groupdict()
                    return self._create_command(cmd_type, params, text)
        
        return None
    
    def _create_command(
        self,
        cmd_type: str,
        params: Dict,
        raw_text: str
    ) -> Command:
        """Create command from parsed parameters."""
        parameters = {}
        
        if 'location' in params:
            loc_name = params['location'].lower()
            if loc_name in self.LOCATIONS:
                loc = self.LOCATIONS[loc_name]
                parameters['lat'] = loc['lat']
                parameters['lon'] = loc['lon']
                parameters['alt'] = loc.get('alt', 30)
        
        if 'speed' in params:
            speed_name = params['speed'].lower()
            if speed_name in self.SPEEDS:
                parameters['speed'] = self.SPEEDS[speed_name]
        
        if 'alt' in params:
            try:
                parameters['alt'] = int(params['alt'])
            except ValueError:
                pass
        
        return Command(
            command_type=cmd_type,
            parameters=parameters,
            raw_text=raw_text,
            confidence=1.0,
            timestamp=time.time()
        )


class SafetyChecker:
    """Validate commands against safety constraints."""
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        
        # Current drone state
        self.current_position: Optional[np.ndarray] = None
        self.home_position: Optional[np.ndarray] = None
        self.current_altitude: float = 0.0
        self.battery_level: float = 1.0
    
    def update_state(
        self,
        position: np.ndarray,
        home_position: np.ndarray,
        battery: float
    ) -> None:
        """Update drone state for safety checks."""
        self.current_position = position
        self.home_position = home_position
        self.battery_level = battery
        self.current_altitude = position[2] if len(position) > 2 else 0
    
    def validate_command(self, command: Command) -> Tuple[bool, Optional[str]]:
        """Validate command against safety constraints.
        
        Args:
            command: Command to validate
            
        Returns:
            (is_safe, error_message)
        """
        if not self.config.enable_safety_checks:
            return True, None
        
        cmd_type = command.command_type
        params = command.parameters
        
        # Check battery
        if self.battery_level < 0.15:
            if cmd_type not in ['land', 'rtl', 'hover']:
                return False, "Battery too low for navigation commands"
        
        # Check altitude
        if 'alt' in params:
            alt = params['alt']
            
            if alt > self.config.max_altitude_command:
                return False, f"Altitude {alt}m exceeds maximum {self.config.max_altitude_command}m"
            
            if alt < 2:
                return False, "Altitude too low (minimum 2m)"
        
        # Check distance from home
        if 'lat' in params and 'lon' in params:
            target = np.array([params['lat'], params['lon']])
            
            if self.home_position is not None:
                home = self.home_position[:2]
                dist = np.linalg.norm(target - home) * 111000  # Approximate meters
                
                if dist > self.config.max_distance_command:
                    return False, f"Distance {dist:.0f}m exceeds maximum {self.config.max_distance_command}m"
        
        # Check for valid command types
        valid_commands = ['goto', 'land', 'rtl', 'takeoff', 'hover', 'circle', 'speed', 'altitude', 'emergency']
        if cmd_type not in valid_commands:
            return False, f"Unknown command type: {cmd_type}"
        
        return True, None


class CommandConfirmation:
    """Handle command confirmation workflow."""
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        
        # Pending confirmation
        self.pending_command: Optional[Command] = None
        self.confirm_deadline: float = 0.0
        self.confirmation_callback: Optional[Callable] = None
    
    def request_confirmation(
        self,
        command: Command,
        callback: Callable[[bool], None]
    ) -> None:
        """Request confirmation for command.
        
        Args:
            command: Command to confirm
            callback: Function to call with confirmation result
        """
        if not self.config.require_confirmation:
            # Auto-confirm
            callback(True)
            return
        
        self.pending_command = command
        self.confirm_deadline = time.time() + self.config.confirmation_timeout
        self.confirmation_callback = callback
        
        # In real implementation, would speak confirmation prompt
        print(f"Confirm command: {command.raw_text}")
    
    def confirm(self, yes: bool) -> bool:
        """Process confirmation response.
        
        Args:
            yes: True if confirmed, False if rejected
            
        Returns:
            True if confirmation was processed
        """
        if self.pending_command is None:
            return False
        
        if self.confirmation_callback:
            self.confirmation_callback(yes)
        
        self.pending_command = None
        self.confirmation_callback = None
        
        return True
    
    def check_timeout(self) -> bool:
        """Check if confirmation timed out.
        
        Returns:
            True if timed out
        """
        if self.pending_command is None:
            return False
        
        if time.time() > self.confirm_deadline:
            self.pending_command = None
            self.confirmation_callback = None
            return True
        
        return False


class VoiceCommandSystem:
    """Complete voice command system."""
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        
        # Components
        self.parser = CommandParser(config)
        self.safety_checker = SafetyChecker(config)
        self.confirmation = CommandConfirmation(config)
        
        # Command history
        self.command_history: List[Command] = []
        self.max_history = 100
        
        # Callbacks
        self.on_command_ready: Optional[Callable[[Command], None]] = None
        self.on_command_executed: Optional[Callable[[Command], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
    
    def process_voice_input(self, text: str) -> Optional[Command]:
        """Process voice input text.
        
        Args:
            text: Transcribed voice text
            
        Returns:
            Command object or None
        """
        # Remove wake word if present
        text = self._remove_wake_word(text)
        
        if not text:
            return None
        
        # Parse command
        command = self.parser.parse(text)
        
        if command is None:
            if self.on_error:
                self.on_error(f"Could not understand command: {text}")
            return None
        
        # Safety check
        is_safe, error = self.safety_checker.validate_command(command)
        
        if not is_safe:
            command.error = error
            if self.on_error:
                self.on_error(error)
            return command
        
        # Request confirmation
        if self.config.require_confirmation:
            self.confirmation.request_confirmation(
                command,
                lambda confirmed: self._on_confirmation(command, confirmed)
            )
        else:
            self._execute_command(command)
        
        return command
    
    def _remove_wake_word(self, text: str) -> str:
        """Remove wake word from text."""
        wake = self.config.wake_word.lower()
        
        # Remove wake word from beginning
        text_lower = text.lower()
        
        if text_lower.startswith(wake):
            text = text[len(wake):].strip()
        
        # Also handle "hey skycore" etc.
        patterns = [
            f'hey\\s*{wake}',
            f'ok\\s*{wake}',
            f'okay\\s*{wake}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                start = match.start()
                text = text[:start] + text[match.end():]
                break
        
        return text.strip()
    
    def _on_confirmation(self, command: Command, confirmed: bool) -> None:
        """Handle confirmation result."""
        if confirmed:
            self._execute_command(command)
        else:
            command.error = "Command rejected by user"
            if self.on_error:
                self.on_error("Command cancelled")
    
    def _execute_command(self, command: Command) -> None:
        """Execute validated command."""
        command.confirmed = True
        
        # Add to history
        self.command_history.append(command)
        if len(self.command_history) > self.max_history:
            self.command_history.pop(0)
        
        # Execute via callback
        if self.on_command_ready:
            self.on_command_ready(command)
    
    def confirm_last(self, yes: bool) -> None:
        """Confirm or reject last pending command."""
        self.confirmation.confirm(yes)
    
    def update_drone_state(
        self,
        position: np.ndarray,
        home_position: np.ndarray,
        battery: float
    ) -> None:
        """Update drone state for safety checks."""
        self.safety_checker.update_state(position, home_position, battery)
    
    def get_command_history(self) -> List[Command]:
        """Get command history."""
        return self.command_history.copy()
    
    def add_location(self, name: str, lat: float, lon: float, alt: float = 30) -> None:
        """Add named location for voice commands."""
        self.parser.LOCATIONS[name.lower()] = {'lat': lat, 'lon': lon, 'alt': alt}


def demo_voice():
    """Demonstrate voice command processing."""
    print("=" * 60)
    print("Voice Command System Demo")
    print("=" * 60)
    
    # Create system
    config = VoiceConfig(require_confirmation=False)  # Skip confirmation for demo
    system = VoiceCommandSystem(config)
    
    # Add locations
    system.add_location('tower', 32.0900, 34.7800, 50)
    system.add_location('field', 32.0750, 34.7950, 25)
    
    # Update state
    system.update_drone_state(
        position=np.array([32.0853, 34.7818, 30]),
        home_position=np.array([32.0853, 34.7818, 0]),
        battery=0.75
    )
    
    # Command handlers
    def on_command_ready(cmd: Command):
        print(f"  Command ready: {cmd.command_type}")
        print(f"    Parameters: {cmd.parameters}")
        cmd.executed = True
        if system.on_command_executed:
            system.on_command_executed(cmd)
    
    system.on_command_ready = on_command_ready
    
    # Test commands
    test_commands = [
        "go to home",
        "fly to tower",
        "land",
        "return to home",
        "takeoff",
        "hover",
        "set speed to fast",
        "altitude 50",
        "go to field",
        "emergency land",
    ]
    
    print("\nProcessing voice commands:")
    for cmd_text in test_commands:
        print(f"\nInput: \"{cmd_text}\"")
        
        command = system.process_voice_input(cmd_text)
        
        if command:
            print(f"  Parsed: {command.command_type}")
            print(f"  Confirmed: {command.confirmed}")
            print(f"  Executed: {command.executed}")
            
            if command.error:
                print(f"  Error: {command.error}")
        else:
            print("  Not recognized")
    
    # Show history
    print("\n" + "=" * 40)
    print("Command History")
    print("=" * 40)
    
    history = system.get_command_history()
    for i, cmd in enumerate(history[-5:], 1):
        print(f"  {i}. {cmd.command_type}: {cmd.raw_text} ({'executed' if cmd.executed else 'pending'})")
    
    # Safety check demo
    print("\n" + "=" * 40)
    print("Safety Check Demo")
    print("=" * 40)
    
    system.update_drone_state(
        position=np.array([32.0853, 34.7818, 50]),
        home_position=np.array([32.0853, 34.7818, 0]),
        battery=0.1  # Low battery
    )
    
    cmd = system.parser.parse("go to tower")
    if cmd:
        is_safe, error = system.safety_checker.validate_command(cmd)
        print(f"  Command: {cmd.command_type}")
        print(f"  Safe: {is_safe}")
        if error:
            print(f"  Error: {error}")


if __name__ == "__main__":
    demo_voice()