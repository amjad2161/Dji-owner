"""
SkyCore Voice NLP Module
========================
Voice command recognition using OpenAI Whisper + NLP command parsing.
"""

import asyncio
import logging
import re
import json
import numpy as np
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import struct

log = logging.getLogger(__name__)


class CommandIntent(Enum):
    """Voice command intents."""
    TAKEOFF = "takeoff"
    LAND = "land"
    RTL = "rtl"
    PAUSE = "pause"
    RESUME = "resume"
    GOTO = "goto"
    ORBIT = "orbit"
    FOLLOW = "follow"
    STOP_FOLLOW = "stop_follow"
    PHOTO = "photo"
    VIDEO_START = "video_start"
    VIDEO_STOP = "video_stop"
    HOME = "home"
    STATUS = "status"
    EMERGENCY = "emergency"
    UNKNOWN = "unknown"


@dataclass
class VoiceCommand:
    """Parsed voice command."""
    intent: CommandIntent
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    
    def __str__(self):
        return f"{self.intent.value} (conf={self.confidence:.2f}) entities={self.entities}"


@dataclass
class WhisperResult:
    """Whisper transcription result."""
    text: str
    language: Optional[str] = None
    duration: float = 0.0
    tokens: List[int] = field(default_factory=list)


class VoiceNLP:
    """
    Voice NLP processing with Whisper STT and command parsing.
    
    Supports:
    - Real-time audio stream processing
    - Multi-language command recognition
    - Natural language understanding
    - Command confirmation
    """
    
    def __init__(self, model_size: str = "base", language: str = "en",
                 audio_threshold: float = 0.01, sample_rate: int = 16000):
        """
        Initialize Voice NLP.
        
        Args:
            model_size: Whisper model size (tiny/base/small/medium/large)
            language: Primary language for recognition
            audio_threshold: Minimum audio level to trigger processing
            sample_rate: Audio sample rate (Hz)
        """
        self.model_size = model_size
        self.language = language
        self.audio_threshold = audio_threshold
        self.sample_rate = sample_rate
        
        self.model = None
        self._initialized = False
        
        # Command patterns
        self._command_patterns = self._build_command_patterns()
        
        # Command handlers
        self._handlers: Dict[CommandIntent, List[Callable]] = {}
        
        # Audio buffer for streaming
        self._audio_buffer = bytearray()
        self._buffer_max_samples = sample_rate * 30  # 30 seconds max
        
        # Statistics
        self.commands_processed = 0
        self.confidence_avg = 0.0
        
        log.info(f"VoiceNLP initialized with {model_size} model")
    
    def _build_command_patterns(self) -> Dict[CommandIntent, List[re.Pattern]]:
        """Build regex patterns for command matching."""
        patterns = {
            CommandIntent.TAKEOFF: [
                re.compile(r'\b(take\s*off|起飞|takeoff|take off|lift off|liftoff)\b', re.I),
                re.compile(r'\b(start|begin|go)\b.*\b(fly|flight)\b', re.I),
            ],
            CommandIntent.LAND: [
                re.compile(r'\b(land|降落|landing)\b', re.I),
                re.compile(r'\b(come\s*down|descend)\b', re.I),
            ],
            CommandIntent.RTL: [
                re.compile(r'\b(return\s*to\s*home|rtl|返回|RTH|go home)\b', re.I),
            ],
            CommandIntent.PAUSE: [
                re.compile(r'\b(pause|stop|hold|暂停)\b', re.I),
                re.compile(r'\b(wait|freeze)\b', re.I),
            ],
            CommandIntent.RESUME: [
                re.compile(r'\b(resume|continue|继续|go)\b', re.I),
                re.compile(r'\b(carry\s*on|keep\s*going)\b', re.I),
            ],
            CommandIntent.GOTO: [
                re.compile(r'\b(go\s*to|fly\s*to|move\s*to|前往|goto)\b', re.I),
                re.compile(r'\b(navigate\s*to)\b', re.I),
            ],
            CommandIntent.ORBIT: [
                re.compile(r'\b(orbit|circle|盘旋|rotate)\b', re.I),
                re.compile(r'\b(circle\s*around)\b', re.I),
            ],
            CommandIntent.FOLLOW: [
                re.compile(r'\b(follow|跟踪|track|pursue)\b', re.I),
                re.compile(r'\b(stay\s*behind|stick\s*with)\b', re.I),
            ],
            CommandIntent.STOP_FOLLOW: [
                re.compile(r'\b(stop\s*follow|停止跟踪|end\s*follow)\b', re.I),
                re.compile(r'\b(unfollow|detach)\b', re.I),
            ],
            CommandIntent.PHOTO: [
                re.compile(r'\b(photo|snapshot|capture|拍照|take\s*a\s*photo)\b', re.I),
                re.compile(r'\b(record\s*photo)\b', re.I),
            ],
            CommandIntent.VIDEO_START: [
                re.compile(r'\b(start\s*(video|recording)|begin\s*record|start\s*filming)\b', re.I),
            ],
            CommandIntent.VIDEO_STOP: [
                re.compile(r'\b(stop\s*(video|recording)|end\s*record|stop\s*filming)\b', re.I),
            ],
            CommandIntent.HOME: [
                re.compile(r'\b(set\s*home|set\s*home\s*point|设置家点)\b', re.I),
            ],
            CommandIntent.STATUS: [
                re.compile(r'\b(status|状态|check|how\s*(is|are)|information)\b', re.I),
                re.compile(r'\b(health|battery|position)\b', re.I),
            ],
            CommandIntent.EMERGENCY: [
                re.compile(r'\b(emergency|emergency\s*land|immediate\s*land)\b', re.I),
                re.compile(r'\b(abort|cancel|stop\s*everything)\b', re.I),
            ],
        }
        return patterns
    
    async def initialize(self):
        """Initialize Whisper model."""
        if self._initialized:
            return
        
        try:
            # Import whisper
            import whisper
            self.model = whisper.load_model(self.model_size)
            self._initialized = True
            log.info(f"Whisper model '{self.model_size}' loaded")
        except ImportError:
            log.warning("OpenAI Whisper not installed. Using fallback pattern matching.")
            self._initialized = True  # Allow fallback mode
    
    async def transcribe_audio(self, audio_data: bytes) -> WhisperResult:
        """
        Transcribe audio data to text.
        
        Args:
            audio_data: Raw audio bytes (should be 16-bit PCM)
            
        Returns:
            WhisperResult with transcription
        """
        if not self._initialized:
            await self.initialize()
        
        # Convert to numpy array
        import numpy as np
        
        # Ensure proper format (16-bit PCM)
        samples = np.frombuffer(audio_data, dtype=np.int16)
        samples = samples.astype(np.float32) / 32768.0
        
        if len(samples) < self.sample_rate * 0.5:  # Less than 0.5 seconds
            return WhisperResult(text="", duration=0.0)
        
        if self.model is not None:
            # Use Whisper model
            try:
                result = self.model.transcribe(samples, language=self.language)
                return WhisperResult(
                    text=result["text"].strip(),
                    language=result.get("language"),
                    duration=result.get("duration", 0.0),
                    tokens=result.get("tokens", [])
                )
            except Exception as e:
                log.error(f"Whisper transcription failed: {e}")
        
        # Fallback: return empty if no model
        return WhisperResult(text="", duration=len(samples) / self.sample_rate)
    
    async def process_audio_stream(self, audio_chunk: bytes) -> Optional[VoiceCommand]:
        """
        Process audio stream chunk.
        
        Args:
            audio_chunk: Audio data chunk
            
        Returns:
            VoiceCommand if command detected, None otherwise
        """
        # Add to buffer
        self._audio_buffer.extend(audio_chunk)
        
        # Keep buffer size limited
        if len(self._audio_buffer) > self._buffer_max_samples * 2:
            self._audio_buffer = self._audio_buffer[-self._buffer_max_samples * 2:]
        
        # Calculate audio level
        import numpy as np
        samples = np.frombuffer(bytes(self._audio_buffer), dtype=np.int16)
        if len(samples) > 0:
            rms = np.sqrt(np.mean(samples.astype(np.float32)**2))
            audio_level = rms / 32768.0
        else:
            audio_level = 0.0
        
        # Only process if above threshold
        if audio_level < self.audio_threshold:
            return None
        
        # Look for voice activity (simple VAD)
        if not self._detect_voice_activity(samples):
            return None
        
        # Transcribe
        result = await self.transcribe_audio(bytes(self._audio_buffer[-self.sample_rate * 5:]))  # Last 5 seconds
        
        if not result.text or len(result.text) < 2:
            return None
        
        # Parse command
        command = self.parse_command(result.text)
        
        if command.confidence > 0.5:
            self.commands_processed += 1
            self.confidence_avg = (self.confidence_avg * (self.commands_processed - 1) + command.confidence) / self.commands_processed
            self._audio_buffer.clear()
            return command
        
        return None
    
    def _detect_voice_activity(self, samples: np.ndarray) -> bool:
        """Simple voice activity detection."""
        if len(samples) < 1600:  # 100ms
            return False
        
        # Check energy in frames
        frame_size = 1600  # 100ms frames
        energy_frames = 0
        
        for i in range(0, len(samples) - frame_size, frame_size):
            frame = samples[i:i + frame_size]
            energy = np.sqrt(np.mean(frame.astype(np.float32)**2))
            if energy > 0.02:  # Voice threshold
                energy_frames += 1
        
        # Consider voice if 3+ frames have energy
        return energy_frames >= 3
    
    def parse_command(self, text: str) -> VoiceCommand:
        """
        Parse text to voice command.
        
        Args:
            text: Transcribed text
            
        Returns:
            VoiceCommand with intent and entities
        """
        text_lower = text.lower().strip()
        
        best_intent = CommandIntent.UNKNOWN
        best_confidence = 0.0
        entities = {}
        
        # Try pattern matching
        for intent, patterns in self._command_patterns.items():
            for pattern in patterns:
                match = pattern.search(text_lower)
                if match:
                    confidence = 0.6 + 0.1 * len(match.group())
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_intent = intent
                        entities = self._extract_entities(text_lower, intent)
        
        # Extract numbers for distance/altitude
        if 'לך ל' in text or 'go to' in text_lower or 'fly to' in text_lower:
            numbers = re.findall(r'\d+', text)
            if numbers:
                entities['distance'] = float(numbers[0])
        
        return VoiceCommand(
            intent=best_intent,
            confidence=best_confidence,
            entities=entities,
            raw_text=text
        )
    
    def _extract_entities(self, text: str, intent: CommandIntent) -> Dict[str, Any]:
        """Extract entities from command text."""
        entities = {}
        
        # Numbers
        numbers = re.findall(r'\d+(?:\.\d+)?', text)
        if numbers:
            entities['numbers'] = [float(n) for n in numbers]
        
        # Direction words
        if any(w in text for w in ['north', 'northward', 'צפון', 'up']):
            entities['direction'] = 'north'
        elif any(w in text for w in ['south', 'southward', 'דרום', 'down']):
            entities['direction'] = 'south'
        elif any(w in text for w in ['east', 'eastward', 'מזרח', 'right']):
            entities['direction'] = 'east'
        elif any(w in text for w in ['west', 'westward', 'מערב', 'left']):
            entities['direction'] = 'west'
        
        # Distance units
        if 'meter' in text or 'מטר' in text or 'm' in text:
            entities['unit'] = 'meters'
        elif 'kilometer' in text or 'קילומטר' in text or 'km' in text:
            entities['unit'] = 'kilometers'
        elif 'feet' in text or 'ft' in text:
            entities['unit'] = 'feet'
        
        # Speed
        if 'slow' in text or 'chill' in text or 'איטי' in text:
            entities['speed'] = 'slow'
        elif 'fast' in text or 'quick' in text or 'מהיר' in text:
            entities['speed'] = 'fast'
        
        return entities
    
    def on_command(self, intent: CommandIntent) -> Callable:
        """Decorator to register command handler."""
        def decorator(func: Callable) -> Callable:
            if intent not in self._handlers:
                self._handlers[intent] = []
            self._handlers[intent].append(func)
            return func
        return decorator
    
    async def execute_command(self, command: VoiceCommand, drone=None) -> Dict[str, Any]:
        """
        Execute voice command on drone.
        
        Args:
            command: Parsed voice command
            drone: Drone instance
            
        Returns:
            Execution result
        """
        if command.intent == CommandIntent.UNKNOWN:
            return {'success': False, 'reason': 'Unknown command', 'text': command.raw_text}
        
        # Execute handlers
        results = []
        if command.intent in self._handlers:
            for handler in self._handlers[command.intent]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        result = await handler(command, drone)
                    else:
                        result = handler(command, drone)
                    results.append(result)
                except Exception as e:
                    log.error(f"Command handler error: {e}")
                    results.append({'success': False, 'error': str(e)})
        
        # Default drone commands
        if drone and not results:
            try:
                if command.intent == CommandIntent.TAKEOFF:
                    await drone.takeoff()
                    results.append({'success': True, 'action': 'takeoff'})
                elif command.intent == CommandIntent.LAND:
                    await drone.land()
                    results.append({'success': True, 'action': 'land'})
                elif command.intent == CommandIntent.RTL:
                    await drone.return_to_home()
                    results.append({'success': True, 'action': 'rtl'})
                elif command.intent == CommandIntent.PAUSE:
                    await drone.set_velocity(0, 0, 0)
                    results.append({'success': True, 'action': 'pause'})
                elif command.intent == CommandIntent.PHOTO:
                    await drone.capture_photo()
                    results.append({'success': True, 'action': 'photo'})
                elif command.intent == CommandIntent.VIDEO_START:
                    await drone.start_video_recording()
                    results.append({'success': True, 'action': 'video_start'})
                elif command.intent == CommandIntent.VIDEO_STOP:
                    await drone.stop_video_recording()
                    results.append({'success': True, 'action': 'video_stop'})
            except Exception as e:
                log.error(f"Drone command execution failed: {e}")
                results.append({'success': False, 'error': str(e)})
        
        return {
            'command': command.intent.value,
            'confidence': command.confidence,
            'raw_text': command.raw_text,
            'results': results,
            'success': any(r.get('success', False) for r in results) if results else False
        }
    
    async def stream_from_microphone(self, device_index: int = 0,
                                     callback: Optional[Callable] = None) -> asyncio.Task:
        """
        Stream audio from microphone and process.
        
        Args:
            device_index: Microphone device index
            callback: Optional callback for processed commands
            
        Returns:
            Async task for the stream
        """
        import pyaudio
        
        async def audio_stream():
            p = pyaudio.PyAudio()
            
            try:
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=1024
                )
                
                log.info(f"Listening on microphone {device_index}")
                
                while True:
                    try:
                        data = stream.read(1024, exception_on_overflow=False)
                        command = await self.process_audio_stream(data)
                        
                        if command and callback:
                            await callback(command)
                    except Exception as e:
                        log.error(f"Audio stream error: {e}")
                        await asyncio.sleep(0.1)
                        
            finally:
                stream.stop_stream()
                stream.close()
                p.terminate()
        
        return asyncio.create_task(audio_stream())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get NLP statistics."""
        return {
            'commands_processed': self.commands_processed,
            'average_confidence': round(self.confidence_avg, 3),
            'model_loaded': self.model is not None,
            'model_size': self.model_size,
            'supported_intents': [i.value for i in CommandIntent],
            'handlers_registered': {i.value: len(h) for i, h in self._handlers.items()}
        }


class VoiceCommandSession:
    """Voice command session with confirmation."""
    
    def __init__(self, nlp: VoiceNLP, require_confirmation: bool = False):
        """
        Initialize session.
        
        Args:
            nlp: VoiceNLP instance
            require_confirmation: Require voice confirmation before execution
        """
        self.nlp = nlp
        self.require_confirmation = require_confirmation
        self.pending_command: Optional[VoiceCommand] = None
        self.confirmation_responses = ['yes', 'confirm', 'execute', 'כן', 'אישור', 'go', 'do it']
        self.rejection_responses = ['no', 'cancel', 'abort', 'לא', 'ביטול']
    
    async def process(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Process audio and potentially execute command.
        
        Args:
            audio_data: Audio data
            
        Returns:
            Execution result or None
        """
        command = await self.nlp.process_audio_stream(audio_data)
        
        if not command:
            return None
        
        # If confirmation required and we have pending command
        if self.require_confirmation and self.pending_command:
            text_lower = command.raw_text.lower()
            
            if any(r in text_lower for r in self.confirmation_responses):
                result = await self.nlp.execute_command(self.pending_command)
                self.pending_command = None
                result['confirmed'] = True
                return result
            elif any(r in text_lower for r in self.rejection_responses):
                self.pending_command = None
                return {
                    'confirmed': False,
                    'action': 'cancelled',
                    'original_command': self.pending_command.raw_text
                }
        
        # Check if high enough confidence
        if command.confidence > 0.8:
            return await self.nlp.execute_command(command)
        elif command.confidence > 0.5:
            # Store as pending, ask for confirmation
            self.pending_command = command
            return {
                'needs_confirmation': True,
                'command': command.intent.value,
                'confidence': command.confidence,
                'text': command.raw_text
            }
        
        return None


# Export classes
__all__ = ['VoiceNLP', 'VoiceCommand', 'CommandIntent', 'VoiceCommandSession', 'WhisperResult']