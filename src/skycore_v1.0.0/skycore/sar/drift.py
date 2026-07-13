"""
SkyCore SAR - Drift Analysis
============================
Drift analysis for floating target search and rescue operations.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

log = logging.getLogger(__name__)


class DriftModel(Enum):
    """Drift prediction models."""
    CONSTANT = "constant"  # Constant velocity drift
    WIND = "wind"  # Wind-driven drift
    TIDAL = "tidal"  # Tidal current drift
    DECAY = "decay"  # Decaying drift velocity
    COMBINED = "combined"  # Combined environmental model


@dataclass
class DriftState:
    """Drift prediction state."""
    lat: float
    lon: float
    velocity_east_m_s: float
    velocity_north_m_s: float
    timestamp: float
    confidence: float = 1.0
    source: str = "manual"
    
    def to_dict(self) -> Dict:
        return {
            'lat': self.lat, 'lon': self.lon,
            'velocity_east': self.velocity_east_m_s,
            'velocity_north': self.velocity_north_m_s,
            'timestamp': self.timestamp,
            'confidence': self.confidence,
            'source': self.source
        }


@dataclass
class EnvironmentalConditions:
    """Environmental conditions for drift prediction."""
    wind_speed_m_s: float = 0.0
    wind_direction_deg: float = 0.0  # Direction wind is coming from
    wind_heading_deg: float = 0.0  # Direction wind is going to
    current_speed_m_s: float = 0.0
    current_direction_deg: float = 0.0
    wave_height_m: float = 0.0
    temperature_c: float = 20.0
    humidity_percent: float = 50.0
    
    @property
    def wind_vector(self) -> Tuple[float, float]:
        """Get wind vector (east, north) in m/s."""
        heading_rad = np.radians(self.wind_heading_deg)
        return (
            self.wind_speed_m_s * np.sin(heading_rad),
            self.wind_speed_m_s * np.cos(heading_rad)
        )
    
    @property
    def current_vector(self) -> Tuple[float, float]:
        """Get current vector (east, north) in m/s."""
        heading_rad = np.radians(self.current_direction_deg)
        return (
            self.current_speed_m_s * np.sin(heading_rad),
            self.current_speed_m_s * np.cos(heading_rad)
        )


@dataclass
class DriftPrediction:
    """Drift prediction result."""
    predicted_lat: float
    predicted_lon: float
    prediction_time: float
    search_radius_m: float
    confidence: float
    uncertainty_m: float
    method: DriftModel
    
    def to_dict(self) -> Dict:
        return {
            'lat': self.predicted_lat,
            'lon': self.predicted_lon,
            'time': self.prediction_time,
            'search_radius_m': self.search_radius_m,
            'confidence': self.confidence,
            'uncertainty_m': self.uncertainty_m,
            'method': self.method.value
        }


class DriftAnalyzer:
    """
    Drift analyzer for SAR floating target operations.
    
    Models drift of objects in water based on:
    - Initial position and velocity
    - Wind conditions
    - Tidal/current effects
    - Object properties (buoyancy, drag)
    
    Features:
    - Multiple drift models
    - Environmental data integration
    - Uncertainty estimation
    - Search area calculation
    """
    
    def __init__(self, model: DriftModel = DriftModel.COMBINED):
        """
        Initialize drift analyzer.
        
        Args:
            model: Drift prediction model to use
        """
        self.model = model
        
        # Constants
        self.m_per_deg_lat = 111320
        self.water_drag_coefficient = 0.03  # Typical for person/object in water
        self.wind_factor = 0.02  # Wind effect factor on water surface
        
        # Default environmental conditions
        self.env_conditions = EnvironmentalConditions()
        
        # Statistics
        self.predictions_made = 0
        self.last_prediction: Optional[DriftPrediction] = None
        
        log.info(f"Drift analyzer initialized with model: {model.value}")
    
    def set_environmental_conditions(self, conditions: EnvironmentalConditions):
        """Set environmental conditions for prediction."""
        self.env_conditions = conditions
        log.debug(f"Environmental conditions updated: wind={conditions.wind_speed_m_s}m/s, "
                 f"current={conditions.current_speed_m_s}m/s")
    
    def predict(self, initial_state: DriftState, prediction_time: float,
               object_type: str = "person") -> DriftPrediction:
        """
        Predict drift position at future time.
        
        Args:
            initial_state: Initial drift state
            prediction_time: Time to predict (seconds from initial)
            object_type: Type of object (person, debris, vessel)
            
        Returns:
            DriftPrediction with predicted position
        """
        self.predictions_made += 1
        
        # Get object-specific parameters
        drag_coefficient = self._get_drag_coefficient(object_type)
        
        # Current velocity components
        v_east = initial_state.velocity_east_m_s
        v_north = initial_state.velocity_north_m_s
        
        # Add environmental drift
        env_east, env_north = self._calculate_environmental_drift(drag_coefficient)
        
        v_east += env_east
        v_north += env_north
        
        # Apply model-specific prediction
        if self.model == DriftModel.CONSTANT:
            final_east, final_north, uncertainty = self._predict_constant(
                initial_state.lat, initial_state.lon, v_east, v_north, prediction_time
            )
        elif self.model == DriftModel.WIND:
            final_east, final_north, uncertainty = self._predict_wind(
                initial_state.lat, initial_state.lon, v_east, v_north, prediction_time
            )
        elif self.model == DriftModel.DECAY:
            final_east, final_north, uncertainty = self._predict_decay(
                initial_state.lat, initial_state.lon, v_east, v_north, prediction_time
            )
        else:  # COMBINED or TIDAL
            final_east, final_north, uncertainty = self._predict_combined(
                initial_state.lat, initial_state.lon, v_east, v_north, prediction_time
            )
        
        # Calculate position
        m_per_deg_lon = self.m_per_deg_lat * np.cos(np.radians(initial_state.lat))
        
        delta_lat = final_north / self.m_per_deg_lat
        delta_lon = final_east / m_per_deg_lon
        
        predicted_lat = initial_state.lat + delta_lat
        predicted_lon = initial_state.lon + delta_lon
        
        # Calculate search radius
        search_radius = self._calculate_search_radius(prediction_time, uncertainty)
        
        # Calculate confidence (decreases with time)
        base_confidence = initial_state.confidence
        time_decay = np.exp(-prediction_time / 7200)  # Half-life of ~2 hours
        confidence = base_confidence * (0.5 + 0.5 * time_decay)
        
        prediction = DriftPrediction(
            predicted_lat=predicted_lat,
            predicted_lon=predicted_lon,
            prediction_time=prediction_time,
            search_radius_m=search_radius,
            confidence=confidence,
            uncertainty_m=uncertainty,
            method=self.model
        )
        
        self.last_prediction = prediction
        
        return prediction
    
    def _get_drag_coefficient(self, object_type: str) -> float:
        """Get drag coefficient for object type."""
        coefficients = {
            'person': 0.03,
            'debris': 0.05,
            'vessel': 0.1,
            'buoy': 0.02,
            'raft': 0.04
        }
        return coefficients.get(object_type, 0.03)
    
    def _calculate_environmental_drift(self, drag_coefficient: float) -> Tuple[float, float]:
        """Calculate drift from environmental factors."""
        # Wind drift
        wind_east, wind_north = self.env_conditions.wind_vector
        wind_effect = wind_east * self.wind_factor * drag_coefficient, \
                      wind_north * self.wind_factor * drag_coefficient
        
        # Current drift
        current_east, current_north = self.env_conditions.current_vector
        
        return (wind_effect[0] + current_east, wind_effect[1] + current_north)
    
    def _predict_constant(self, lat: float, lon: float, 
                          v_east: float, v_north: float, 
                          dt: float) -> Tuple[float, float, float]:
        """Constant velocity prediction."""
        delta_east = v_east * dt
        delta_north = v_north * dt
        
        # Uncertainty grows with time
        uncertainty = 50 + 10 * dt / 60  # 50m base + 10m per minute
        
        return delta_east, delta_north, uncertainty
    
    def _predict_wind(self, lat: float, lon: float,
                      v_east: float, v_north: float,
                      dt: float) -> Tuple[float, float, float]:
        """Wind-driven drift prediction."""
        # Apply wind decay over time
        wind_factor = np.exp(-dt / 3600)  # Decay over 1 hour
        
        wind_east, wind_north = self.env_conditions.wind_vector
        
        # Combined velocity with decay
        total_v_east = v_east + wind_east * wind_factor * self.wind_factor
        total_v_north = v_north + wind_north * wind_factor * self.wind_factor
        
        delta_east = total_v_east * dt
        delta_north = total_v_north * dt
        
        # Higher uncertainty for wind model
        uncertainty = 100 + 20 * dt / 60
        
        return delta_east, delta_north, uncertainty
    
    def _predict_decay(self, lat: float, lon: float,
                       v_east: float, v_north: float,
                       dt: float) -> Tuple[float, float, float]:
        """Decaying velocity drift prediction."""
        # Decay factor
        decay = np.exp(-dt / 1800)  # 30 minute decay time
        
        # Integrate decaying velocity
        delta_east = v_east * dt * (1 + (1 - decay) * dt / 1800) / 2
        delta_north = v_north * dt * (1 + (1 - decay) * dt / 1800) / 2
        
        uncertainty = 75 + 15 * dt / 60
        
        return delta_east, delta_north, uncertainty
    
    def _predict_combined(self, lat: float, lon: float,
                          v_east: float, v_north: float,
                          dt: float) -> Tuple[float, float, float]:
        """Combined drift model."""
        # Environmental drift
        env_east, env_north = self._calculate_environmental_drift(0.03)
        
        # Time-varying components
        v_east_total = v_east + env_east
        v_north_total = v_north + env_north
        
        # Apply decay to initial velocity
        decay = np.exp(-dt / 3600)
        
        # Integrate
        delta_east = v_east * dt * decay + env_east * dt * 0.5
        delta_north = v_north * dt * decay + env_north * dt * 0.5
        
        # Add current as steady component
        current_east, current_north = self.env_conditions.current_vector
        delta_east += current_east * dt
        delta_north += current_north * dt
        
        uncertainty = 80 + 15 * dt / 60
        
        return delta_east, delta_north, uncertainty
    
    def _calculate_search_radius(self, dt: float, uncertainty: float) -> float:
        """Calculate search radius based on prediction time and uncertainty."""
        # Base radius grows with time
        base_radius = 200 + 50 * dt / 60  # 200m base + 50m per minute
        
        # Add uncertainty
        total_radius = base_radius + uncertainty
        
        return total_radius
    
    def generate_search_grid(self, center: Tuple[float, float],
                            radius_m: float, 
                            grid_spacing_m: float = 100) -> List[Tuple[float, float]]:
        """
        Generate search grid points around predicted location.
        
        Args:
            center: (lat, lon) of center point
            radius_m: Search radius in meters
            grid_spacing_m: Grid spacing in meters
            
        Returns:
            List of (lat, lon) grid points
        """
        lat, lon = center
        m_per_deg_lon = self.m_per_deg_lat * np.cos(np.radians(lat))
        
        points = []
        
        # Calculate grid extent
        extent_lat = radius_m / self.m_per_deg_lat
        extent_lon = radius_m / m_per_deg_lon
        
        # Generate grid
        lat_range = np.arange(-extent_lat, extent_lat + grid_spacing_m / self.m_per_deg_lat, 
                             grid_spacing_m / self.m_per_deg_lat)
        lon_range = np.arange(-extent_lon, extent_lon + grid_spacing_m / m_per_deg_lon,
                             grid_spacing_m / m_per_deg_lon)
        
        for dlat in lat_range:
            for dlon in lon_range:
                # Check if within circle
                dist_m = np.sqrt((dlat * self.m_per_deg_lat)**2 + 
                               (dlon * m_per_deg_lon)**2)
                
                if dist_m <= radius_m:
                    points.append((lat + dlat, lon + dlon))
        
        return points
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get drift analyzer statistics."""
        return {
            'model': self.model.value,
            'predictions_made': self.predictions_made,
            'wind_speed_m_s': self.env_conditions.wind_speed_m_s,
            'current_speed_m_s': self.env_conditions.current_speed_m_s,
            'last_prediction': self.last_prediction.to_dict() if self.last_prediction else None
        }


# Export
__all__ = ['DriftAnalyzer', 'DriftModel', 'DriftState', 'DriftPrediction', 'EnvironmentalConditions']