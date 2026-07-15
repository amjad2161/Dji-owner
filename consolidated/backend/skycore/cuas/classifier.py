"""
SkyCore CUAS - Threat Classifier
================================
Counter-Unmanned Aircraft System threat classification.
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger(__name__)


class ThreatCategory(Enum):
    """Threat categories for classification."""
    UNKNOWN = "unknown"
    BENIGN = "benign"
    COMMERCIAL_DRONE = "commercial_drone"
    MILITARY_UAV = "military_uav"
    HOMEMADE_DRONE = "homemade_drone"
    BIRD = "bird"
    BALLOON = "balloon"
    DECOY = "decoy"
    HOSTILE = "hostile"


class ThreatLevel(Enum):
    """Threat severity levels."""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ThreatFeatures:
    """Extracted threat features for classification."""
    radar_cross_section_db: float = -30.0  # dBsm
    doppler_velocity_m_s: float = 0.0
    altitude_m: float = 0.0
    ground_speed_m_s: float = 0.0
    track_direction_deg: float = 0.0
    size_m: float = 0.0  # Estimated size
    vertical_speed_m_s: float = 0.0
    signal_strength_db: float = -100.0
    frequency_hz: float = 0.0
    jammer_present: bool = False
    transponder_code: Optional[str] = None
    last_seen_sec: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            'rcs_db': self.radar_cross_section_db,
            'doppler_m_s': self.doppler_velocity_m_s,
            'altitude_m': self.altitude_m,
            'speed_m_s': self.ground_speed_m_s,
            'track_deg': self.track_direction_deg,
            'size_m': self.size_m,
            'vsi_m_s': self.vertical_speed_m_s,
            'signal_db': self.signal_strength_db,
            'frequency_hz': self.frequency_hz,
            'jammer': self.jammer_present,
            'transponder': self.transponder_code,
            'age_sec': time.time() - self.last_seen_sec
        }


@dataclass
class ThreatClassification:
    """Threat classification result."""
    category: ThreatCategory
    confidence: float  # 0-1
    threat_level: ThreatLevel
    features: ThreatFeatures
    indicators: List[str] = field(default_factory=list)
    recommended_action: str = ""
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            'category': self.category.value,
            'confidence': self.confidence,
            'threat_level': self.threat_level.value,
            'indicators': self.indicators,
            'action': self.recommended_action,
            'timestamp': self.timestamp
        }


class CUASClassifier:
    """
    Counter-Unmanned Aircraft System (CUAS) threat classifier.
    
    Classifies detected objects as potential threats based on:
    - Radar characteristics (RCS, Doppler)
    - Size and flight profile
    - Electronic signatures
    - Behavioral analysis
    
    Features:
    - Multi-feature classification
    - Confidence scoring
    - Threat level determination
    - Action recommendations
    """
    
    def __init__(self, sensitivity: float = 0.5):
        """
        Initialize CUAS classifier.
        
        Args:
            sensitivity: Classification sensitivity (0-1, higher = more aggressive)
        """
        self.sensitivity = sensitivity
        
        # Classification thresholds
        self.thresholds = {
            'rcs_min_commercial': -25.0,  # dBsm
            'rcs_max_bird': -35.0,
            'speed_max_bird': 15.0,  # m/s
            'speed_min_uav': 2.0,
            'speed_max_uav': 35.0,
            'altitude_max_balloon': 500.0,
            'altitude_min_uav': 10.0,
            'altitude_max_uav': 15000.0
        }
        
        # Statistics
        self.total_classifications = 0
        self.category_counts: Dict[ThreatCategory, int] = {}
        
        log.info(f"CUAS Classifier initialized (sensitivity: {sensitivity})")
    
    def classify(self, features: ThreatFeatures, 
                 context: Optional[Dict] = None) -> ThreatClassification:
        """
        Classify threat based on features.
        
        Args:
            features: Extracted threat features
            context: Optional context (own position, friendly zones, etc.)
            
        Returns:
            ThreatClassification with category and confidence
        """
        self.total_classifications += 1
        
        indicators = []
        scores = {}
        
        # Feature-based scoring
        # RCS scoring
        if features.radar_cross_section_db > self.thresholds['rcs_min_commercial']:
            scores['commercial'] = scores.get('commercial', 0) + 0.3
            indicators.append(f"High RCS: {features.radar_cross_section_db:.1f} dBsm")
        elif features.radar_cross_section_db < self.thresholds['rcs_max_bird']:
            scores['bird'] = scores.get('bird', 0) + 0.4
            indicators.append(f"Very low RCS: {features.radar_cross_section_db:.1f} dBsm")
        
        # Speed scoring
        if self.thresholds['speed_min_uav'] <= features.ground_speed_m_s <= self.thresholds['speed_max_uav']:
            scores['uav'] = scores.get('uav', 0) + 0.3
            indicators.append(f"UAV-like speed: {features.ground_speed_m_s:.1f} m/s")
        
        if features.ground_speed_m_s > self.thresholds['speed_max_bird']:
            scores['uav'] = scores.get('uav', 0) + 0.2
            scores.pop('bird', None)
        
        # Altitude scoring
        if features.altitude_m > self.thresholds['altitude_max_balloon']:
            scores['balloon'] = scores.get('balloon', 0) + 0.3
        
        if self.thresholds['altitude_min_uav'] <= features.altitude_m <= self.thresholds['altitude_max_uav']:
            scores['uav'] = scores.get('uav', 0) + 0.2
        
        # Vertical speed scoring
        if abs(features.vertical_speed_m_s) < 0.5:
            indicators.append("Stationary vertical speed (hovering)")
            scores['uav'] = scores.get('uav', 0) + 0.3
        
        # Size scoring
        if features.size_m > 1.5:
            scores['commercial'] = scores.get('commercial', 0) + 0.2
            indicators.append(f"Large object: {features.size_m:.1f}m")
        elif features.size_m < 0.3:
            scores['bird'] = scores.get('bird', 0) + 0.2
        
        # Jammer detection
        if features.jammer_present:
            indicators.append("Jammer signal detected")
            scores['hostile'] = scores.get('hostile', 0) + 0.5
        
        # Transponder analysis
        if features.transponder_code:
            if features.transponder_code.startswith('75'):
                indicators.append("Emergency transponder code")
                scores['benign'] = scores.get('benign', 0) + 0.5
            else:
                scores['friendly'] = scores.get('friendly', 0) + 0.3
        
        # Determine category
        if not scores:
            category = ThreatCategory.UNKNOWN
            confidence = 0.3
        else:
            max_score = max(scores.values())
            best_match = max(scores, key=scores.get)
            
            confidence = min(1.0, max_score / 2.0)  # Normalize confidence
            
            if best_match == 'uav':
                if features.radar_cross_section_db > -20:
                    category = ThreatCategory.COMMERCIAL_DRONE
                elif features.signal_strength_db > -80:
                    category = ThreatCategory.MILITARY_UAV
                else:
                    category = ThreatCategory.HOMEMADE_DRONE
            elif best_match == 'commercial':          # large / high-RCS object -> commercial drone
                category = ThreatCategory.COMMERCIAL_DRONE
            elif best_match == 'bird':
                category = ThreatCategory.BIRD
            elif best_match == 'balloon':
                category = ThreatCategory.BALLOON
            elif best_match == 'hostile':
                category = ThreatCategory.HOSTILE
            elif best_match == 'friendly':            # transponder-identified -> treat as benign
                category = ThreatCategory.BENIGN
            else:
                category = ThreatCategory.BENIGN
        
        # Threat level determination
        threat_level = self._determine_threat_level(category, confidence, features)
        
        # Action recommendation
        action = self._get_recommended_action(threat_level, category)
        
        self.category_counts[category] = self.category_counts.get(category, 0) + 1
        
        return ThreatClassification(
            category=category,
            confidence=confidence,
            threat_level=threat_level,
            features=features,
            indicators=indicators,
            recommended_action=action
        )
    
    def _determine_threat_level(self, category: ThreatCategory, 
                                 confidence: float,
                                 features: ThreatFeatures) -> ThreatLevel:
        """Determine threat level based on category and features."""
        base_levels = {
            ThreatCategory.BENIGN: ThreatLevel.NONE,
            ThreatCategory.BIRD: ThreatLevel.LOW,
            ThreatCategory.BALLOON: ThreatLevel.LOW,
            ThreatCategory.UNKNOWN: ThreatLevel.MEDIUM,
            ThreatCategory.HOMEMADE_DRONE: ThreatLevel.MEDIUM,
            ThreatCategory.COMMERCIAL_DRONE: ThreatLevel.HIGH,
            ThreatCategory.MILITARY_UAV: ThreatLevel.HIGH,
            ThreatCategory.HOSTILE: ThreatLevel.CRITICAL
        }
        
        base_level = base_levels.get(category, ThreatLevel.MEDIUM)
        
        # Adjust based on confidence and sensitivity
        level_value = base_level.value
        
        if confidence > 0.8:
            level_value += 1  # More confident = higher level
        
        if self.sensitivity > 0.7:
            level_value += 1  # Higher sensitivity = more aggressive
        
        # Adjust based on altitude (lower = higher threat)
        if features.altitude_m < 50:
            level_value = min(4, level_value + 1)
        elif features.altitude_m < 100:
            level_value = min(4, level_value + 0)
        
        return ThreatLevel(max(0, min(4, level_value)))
    
    def _get_recommended_action(self, threat_level: ThreatLevel, 
                                category: ThreatCategory) -> str:
        """Get recommended action based on threat level.

        Detection / alerting ONLY. This is legitimate airspace-awareness software:
        recommendations are operator/authority notification, never any countermeasure.
        """
        actions = {
            ThreatLevel.NONE: "Continue monitoring",
            ThreatLevel.LOW: "Monitor and log",
            ThreatLevel.MEDIUM: "Alert operator, continue tracking",
            ThreatLevel.HIGH: "Alert security, track and notify authorities",
            ThreatLevel.CRITICAL: "Immediate operator alert, escalate to authorities"
        }
        
        return actions.get(threat_level, "Assess situation")
    
    def batch_classify(self, features_list: List[ThreatFeatures],
                      context: Optional[Dict] = None) -> List[ThreatClassification]:
        """Classify multiple threats."""
        return [self.classify(f, context) for f in features_list]
    
    def update_thresholds(self, new_thresholds: Dict[str, float]):
        """Update classification thresholds."""
        self.thresholds.update(new_thresholds)
        log.info("Classification thresholds updated")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get classifier statistics."""
        return {
            'total_classifications': self.total_classifications,
            'category_counts': {k.value: v for k, v in self.category_counts.items()},
            'sensitivity': self.sensitivity,
            'thresholds': self.thresholds
        }


# Export
__all__ = ['CUASClassifier', 'ThreatCategory', 'ThreatLevel', 'ThreatFeatures', 'ThreatClassification']