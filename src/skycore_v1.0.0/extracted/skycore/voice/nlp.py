"""
SkyCore Voice NLP Module
Natural Language Understanding for drone commands
Supports: English, Hebrew, Arabic
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional

class IntentType(str, Enum):
    TAKEOFF = "takeoff"
    LAND = "land"
    RTL = "rtl"
    GOTO = "goto"
    ORBIT = "orbit"
    FOLLOW = "follow"
    EMERGENCY = "emergency"
    STATUS = "status"
    LIGHT_ON = "light_on"
    LIGHT_OFF = "light_off"

@dataclass
class ParsedCommand:
    intent: IntentType
    confidence: float
    parameters: Dict
    original_text: str
    language: str

class VoiceCommandParser:
    """Multi-language voice command parser for SkyCore"""

    def __init__(self):
        self._patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict:
        return {
            'en': {
                IntentType.TAKEOFF: [r'take\s*off', r'launch', r'fly\s*up'],
                IntentType.LAND: [r'land', r'come\s*down', r'set\s*down'],
                IntentType.RTL: [r'return\s*home', r'rtl', r'come\s*back'],
                IntentType.EMERGENCY: [r'stop', r'emergency', r'abort', r'hold'],
                IntentType.GOTO: [r'go\s*to', r'fly\s*to'],
                IntentType.ORBIT: [r'orbit', r'circle\s*around'],
                IntentType.FOLLOW: [r'follow', r'track'],
                IntentType.LIGHT_ON: [r'light\s*on', r'turn\s*on\s*light'],
                IntentType.LIGHT_OFF: [r'light\s*off', r'turn\s*off\s*light'],
            },
            'he': {
                IntentType.TAKEOFF: [r'המריא', r'התרומם', r'טוס'],
                IntentType.LAND: [r'נחת', r'הורד', r'למטה'],
                IntentType.RTL: [r'חזור', r'הביתה', r'חזרה'],
                IntentType.EMERGENCY: [r'עצור', r'חירום', r'הפסק'],
                IntentType.GOTO: [r'טוס ל', r'לך ל'],
                IntentType.ORBIT: [r'הקף', r'סובב'],
                IntentType.FOLLOW: [r'עקוב', r'לעקוב אחרי'],
                IntentType.LIGHT_ON: [r'הדלק אור', r'תאורה'],
                IntentType.LIGHT_OFF: [r'כבה אור', r'כיבוי תאורה'],
            }
        }

    def parse(self, text: str, language: str = 'auto') -> ParsedCommand:
        text_lower = text.lower().strip()
        
        if language == 'auto':
            language = self._detect_language(text_lower)
        
        patterns = self._patterns.get(language, self._patterns['en'])
        
        best_intent = IntentType.STATUS
        best_conf = 0.1
        
        for intent, regex_list in patterns.items():
            for pattern in regex_list:
                if re.search(pattern, text_lower):
                    conf = 0.95
                    if conf > best_conf:
                        best_conf = conf
                        best_intent = intent
        
        params = self._extract_params(text_lower, best_intent)
        
        return ParsedCommand(
            intent=best_intent,
            confidence=best_conf,
            parameters=params,
            original_text=text,
            language=language
        )

    def _detect_language(self, text: str) -> str:
        if any('\u0590' <= c <= '\u05FF' for c in text):
            return 'he'
        if any('\u0600' <= c <= '\u06FF' for c in text):
            return 'ar'
        return 'en'

    def _extract_params(self, text: str, intent: IntentType) -> Dict:
        params = {}
        if intent == IntentType.GOTO:
            coord = re.search(r'(\d+\.?\d*)\s*[,°]\s*(\d+\.?\d*)', text)
            if coord:
                params['lat'] = float(coord.group(1))
                params['lon'] = float(coord.group(2))
        if intent == IntentType.ORBIT:
            radius = re.search(r'(\d+)\s*(m|meter|מטר)', text)
            if radius:
                params['radius_m'] = float(radius.group(1))
        if intent == IntentType.FOLLOW:
            if 'person' in text or 'אדם' in text:
                params['target'] = 'person'
            elif 'car' in text or 'רכב' in text:
                params['target'] = 'car'
        return params

    def generate_confirmation(self, cmd: ParsedCommand) -> str:
        msgs = {
            'en': {
                IntentType.TAKEOFF: "Taking off now",
                IntentType.LAND: "Landing initiated",
                IntentType.RTL: "Returning to home",
                IntentType.EMERGENCY: "Emergency stop activated",
                IntentType.ORBIT: f"Starting orbit with radius {cmd.parameters.get('radius_m', 60)}m",
                IntentType.FOLLOW: f"Following {cmd.parameters.get('target', 'target')}",
            },
            'he': {
                IntentType.TAKEOFF: "ממריא עכשיו",
                IntentType.LAND: "מתחיל נחיתה",
                IntentType.RTL: "חוזר לנקודת ההמראה",
                IntentType.EMERGENCY: "עצירת חירום הופעלה",
                IntentType.ORBIT: f"מקיף ברדיוס {cmd.parameters.get('radius_m', 60)} מטר",
                IntentType.FOLLOW: f"עוקב אחרי {cmd.parameters.get('target', 'המטרה')}",
            }
        }
        return msgs.get(cmd.language, msgs['en']).get(cmd.intent, "Command received")
