"""Voice transcription + simple command grammar.

Wraps OpenAI Whisper (`openai-whisper` or `faster-whisper`) for STT.
This module **does not** auto-execute commands — you wire it up in your
app explicitly. Voice control of an aircraft should always include a
confirmation step.

Grammar:
    skycore takeoff [N meters]
    skycore land
    skycore return
    skycore photo
    skycore record start | stop
    skycore goto <lat> <lon>
    skycore orbit <radius>
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

_NUM = r"-?\d+(?:\.\d+)?"
_TAKEOFF = re.compile(rf"\btake\s*off(?:\s+(?P<alt>{_NUM}))?", re.I)
_LAND = re.compile(r"\bland\b", re.I)
_RETURN = re.compile(r"\b(return|rth|home)\b", re.I)
_PHOTO = re.compile(r"\b(photo|picture|snap)\b", re.I)
_RECORD_START = re.compile(r"\brecord(?:ing)?\s+(start|begin|on)\b", re.I)
_RECORD_STOP = re.compile(r"\brecord(?:ing)?\s+(stop|end|off)\b", re.I)
_GOTO = re.compile(rf"\bgo\s*to\s+(?P<lat>{_NUM})[,\s]+(?P<lon>{_NUM})", re.I)
_ORBIT = re.compile(rf"\borbit(?:\s+(?P<radius>{_NUM}))?", re.I)


@dataclass
class VoiceCommand:
    action: str
    args: dict


def parse_command(text: str) -> Optional[VoiceCommand]:
    """Parse a transcribed utterance. Returns None if no command recognized."""
    if not text:
        return None
    if m := _TAKEOFF.search(text):
        alt = float(m.group("alt")) if m.group("alt") else 5.0
        return VoiceCommand("takeoff", {"altitude": alt})
    if _LAND.search(text):
        return VoiceCommand("land", {})
    if _RETURN.search(text):
        return VoiceCommand("return", {})
    if _PHOTO.search(text):
        return VoiceCommand("photo", {})
    if _RECORD_START.search(text):
        return VoiceCommand("record_start", {})
    if _RECORD_STOP.search(text):
        return VoiceCommand("record_stop", {})
    if m := _GOTO.search(text):
        return VoiceCommand("goto", {"lat": float(m.group("lat")), "lon": float(m.group("lon"))})
    if m := _ORBIT.search(text):
        radius = float(m.group("radius")) if m.group("radius") else 50.0
        return VoiceCommand("orbit", {"radius": radius})
    return None


class VoiceTranscriber:
    """Whisper wrapper. Loads the model lazily."""

    def __init__(self, model_name: str = "base.en", backend: str = "whisper"):
        """backend: 'whisper' for openai-whisper, 'faster-whisper' for the faster fork."""
        self.model_name = model_name
        self.backend = backend
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        if self.backend == "faster-whisper":
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise ImportError("pip install faster-whisper") from e
            self._model = WhisperModel(self.model_name)
        else:
            try:
                import whisper
            except ImportError as e:
                raise ImportError("pip install openai-whisper") from e
            self._model = whisper.load_model(self.model_name)

    def transcribe(self, audio_path: str, language: str = "en") -> str:
        self._load()
        if self.backend == "faster-whisper":
            segments, _ = self._model.transcribe(audio_path, language=language)
            return " ".join(s.text for s in segments).strip()
        return self._model.transcribe(audio_path, language=language)["text"].strip()
