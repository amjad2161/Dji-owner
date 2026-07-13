"""
SkyCore SAR - Heatmap Generation
================================
Generate coverage and probability heatmaps for Search and Rescue operations.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import json

log = logging.getLogger(__name__)


class HeatmapType(Enum):
    """Types of SAR heatmaps."""
    COVERAGE = "coverage"  # Search coverage probability
    PROBABILITY = "probability"  # Target detection probability
    CUMULATIVE = "cumulative"  # Combined coverage over time
    DENSITY = "density"  # Target density estimation
    SWATH = "swath"  # Swath width coverage


@dataclass
class GridCell:
    """Grid cell for heatmap."""
    lat: float
    lon: float
    coverage: float = 0.0  # 0-1 coverage probability
    probability: float = 0.0  # Target probability
    visits: int = 0  # Number of times visited
    last_visit: float = 0.0  # Timestamp of last visit
    
    def to_dict(self) -> Dict:
        return {
            'lat': self.lat, 'lon': self.lon,
            'coverage': self.coverage, 'probability': self.probability,
            'visits': self.visits, 'last_visit': self.last_visit
        }


@dataclass
class HeatmapConfig:
    """Heatmap generation configuration."""
    grid_resolution_m: float = 10.0  # Grid cell size in meters
    coverage_radius_m: float = 50.0  # Camera coverage radius
    search_altitude_m: float = 100.0
    probability_decay: float = 0.95  # Decay factor for old observations
    search_pattern: str = "lawnmower"  # lawnmower, spiral, parallel
    swath_width_m: float = 100.0  # Effective swath width


@dataclass
class HeatmapResult:
    """Result of heatmap generation."""
    heatmap_type: HeatmapType
    grid: List[List[GridCell]]
    bounds: Tuple[float, float, float, float]  # min_lat, min_lon, max_lat, max_lon
    resolution_m: float
    total_cells: int
    covered_cells: int
    coverage_percent: float
    max_probability: float
    timestamp: float
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'type': self.heatmap_type.value,
            'bounds': self.bounds,
            'resolution_m': self.resolution_m,
            'total_cells': self.total_cells,
            'covered_cells': self.covered_cells,
            'coverage_percent': self.coverage_percent,
            'max_probability': self.max_probability,
            'timestamp': self.timestamp,
            'metadata': self.metadata
        }


class SARHeatmapGenerator:
    """
    SAR (Search and Rescue) heatmap generator.
    
    Generates various types of heatmaps for search operations:
    - Coverage heatmaps: Where has been searched
    - Probability heatmaps: Where target is likely to be
    - Cumulative heatmaps: Combined over time
    - Swath heatmaps: Effective coverage area
    
    Features:
    - Multiple search patterns
    - Time-decay modeling
    - Bayesian target probability
    - Grid-based efficient storage
    """
    
    def __init__(self, config: Optional[HeatmapConfig] = None):
        """
        Initialize SAR heatmap generator.
        
        Args:
            config: Heatmap configuration
        """
        self.config = config or HeatmapConfig()
        
        # Grid storage
        self.grid: Dict[Tuple[int, int], GridCell] = {}
        self.grid_size: Tuple[int, int] = (0, 0)
        self.bounds: Tuple[float, float, float, float] = (0, 0, 0, 0)
        
        # Georeferencing
        self.m_per_deg_lat = 111320  # meters per degree latitude
        self.m_per_deg_lon = 0  # varies with latitude
        
        # Statistics
        self.total_observations = 0
        self.last_update_time = 0.0
        
        log.info("SAR Heatmap generator initialized")
    
    def initialize_grid(self, bounds: Tuple[float, float, float, float]):
        """
        Initialize empty grid for area.
        
        Args:
            bounds: (min_lat, min_lon, max_lat, max_lon)
        """
        self.bounds = bounds
        min_lat, min_lon, max_lat, max_lon = bounds
        
        # Calculate grid dimensions
        lat_span = max_lat - min_lat
        lon_span = max_lon - min_lon
        
        self.m_per_deg_lon = self.m_per_deg_lat * np.cos(np.radians((min_lat + max_lat) / 2))
        
        cell_size_lat = self.config.grid_resolution_m / self.m_per_deg_lat
        cell_size_lon = self.config.grid_resolution_m / self.m_per_deg_lon
        
        self.grid_size = (
            int(np.ceil(lat_span / cell_size_lat)),
            int(np.ceil(lon_span / cell_size_lon))
        )
        
        self.grid.clear()
        
        # Create grid cells
        for i in range(self.grid_size[0]):
            for j in range(self.grid_size[1]):
                lat = min_lat + (i + 0.5) * cell_size_lat
                lon = min_lon + (j + 0.5) * cell_size_lon
                
                cell = GridCell(lat=lat, lon=lon)
                self.grid[(i, j)] = cell
        
        log.info(f"Grid initialized: {self.grid_size[0]}x{self.grid_size[1]} cells, "
                f"bounds: {bounds}")
    
    def update_coverage(self, position: Tuple[float, float], timestamp: float,
                       heading: float, footprint: Optional[float] = None):
        """
        Update coverage with new observation position.
        
        Args:
            position: (lat, lon) of drone
            timestamp: Observation timestamp
            heading: Drone heading in degrees
            footprint: Optional custom footprint radius
        """
        lat, lon = position
        radius = footprint or self.config.coverage_radius_m
        
        # Calculate affected cells
        cell_size_lat = self.config.grid_resolution_m / self.m_per_deg_lat
        cell_size_lon = self.config.grid_resolution_m / self.m_per_deg_lon
        
        # Distance in cells
        radius_cells_lat = int(radius / self.config.grid_resolution_m) + 1
        radius_cells_lon = int(radius / (self.m_per_deg_lon * self.config.grid_resolution_m)) + 1
        
        min_lat, min_lon, max_lat, max_lon = self.bounds
        
        # Grid indices
        center_i = int((lat - min_lat) / cell_size_lat)
        center_j = int((lon - min_lon) / cell_size_lon)
        
        # Update cells within radius
        for di in range(-radius_cells_lat, radius_cells_lat + 1):
            for dj in range(-radius_cells_lon, radius_cells_lon + 1):
                i, j = center_i + di, center_j + dj
                
                if (i, j) not in self.grid:
                    continue
                
                cell = self.grid[(i, j)]
                
                # Calculate distance from observation point
                cell_lat = min_lat + (i + 0.5) * cell_size_lat
                cell_lon = min_lon + (j + 0.5) * cell_size_lon
                
                dist = self._haversine_distance(lat, lon, cell_lat, cell_lon)
                
                if dist <= radius:
                    # Coverage contribution based on distance
                    coverage_contribution = 1.0 - (dist / radius)
                    
                    # Update cell
                    cell.coverage = min(1.0, cell.coverage + coverage_contribution)
                    cell.visits += 1
                    cell.last_visit = timestamp
                    
                    self.total_observations += 1
        
        self.last_update_time = timestamp
    
    def update_probability(self, position: Tuple[float, float], detection: bool,
                          target_prior: float = 0.1):
        """
        Update target probability with detection result.
        
        Args:
            position: (lat, lon) of observation
            detection: True if target detected
            target_prior: Prior probability of target
        """
        lat, lon = position
        
        min_lat, min_lon, _, _ = self.bounds
        cell_size_lat = self.config.grid_resolution_m / self.m_per_deg_lat
        cell_size_lon = self.config.grid_resolution_m / self.m_per_deg_lon
        
        i = int((lat - min_lat) / cell_size_lat)
        j = int((lon - min_lon) / cell_size_lon)
        
        if (i, j) not in self.grid:
            return
        
        cell = self.grid[(i, j)]
        
        # Bayesian update
        if detection:
            # Detection increases probability (assume 0.8 detection probability)
            detection_prob = 0.8
            false_alarm_rate = 0.1
            
            # P(target | detection) = P(detection | target) * P(target) / P(detection)
            p_detection_given_target = detection_prob
            p_detection_given_no_target = false_alarm_rate
            
            p_detection = (p_detection_given_target * target_prior + 
                          p_detection_given_no_target * (1 - target_prior))
            
            new_prob = (p_detection_given_target * target_prior) / p_detection
        else:
            # No detection decreases probability
            detection_prob = 0.3  # Lower detection probability at distance
            false_alarm_rate = 0.01
            
            p_no_detection = ((1 - detection_prob) * target_prior + 
                            (1 - false_alarm_rate) * (1 - target_prior))
            
            p_target_given_no_detection = ((1 - detection_prob) * target_prior) / p_no_detection
            
            new_prob = p_target_given_no_detection
        
        cell.probability = new_prob
    
    def apply_time_decay(self, current_time: float, decay_factor: Optional[float] = None):
        """
        Apply time decay to coverage probabilities.
        
        Args:
            current_time: Current timestamp
            decay_factor: Optional override decay factor
        """
        df = decay_factor or self.config.probability_decay
        
        for cell in self.grid.values():
            if cell.last_visit > 0:
                time_diff = current_time - cell.last_visit
                
                # Apply decay based on time
                hours_old = time_diff / 3600
                decay = df ** hours_old
                
                cell.coverage *= decay
    
    def _haversine_distance(self, lat1: float, lon1: float, 
                           lat2: float, lon2: float) -> float:
        """Calculate haversine distance between two points in meters."""
        R = 6371000  # Earth radius in meters
        
        lat1_rad, lat2_rad = np.radians(lat1), np.radians(lat2)
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)
        
        a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        
        return R * c
    
    def generate_heatmap(self, heatmap_type: HeatmapType = HeatmapType.COVERAGE) -> HeatmapResult:
        """
        Generate heatmap result.
        
        Args:
            heatmap_type: Type of heatmap to generate
            
        Returns:
            HeatmapResult with grid data
        """
        # Convert grid to 2D array
        grid_array = [[self.grid.get((i, j), GridCell(0, 0)) 
                       for j in range(self.grid_size[1])] 
                      for i in range(self.grid_size[0])]
        
        # Calculate statistics
        covered_cells = sum(1 for cell in self.grid.values() if cell.coverage > 0)
        total_cells = len(self.grid)
        
        if heatmap_type == HeatmapType.COVERAGE:
            values = [cell.coverage for cell in self.grid.values()]
        else:
            values = [cell.probability for cell in self.grid.values()]
        
        max_prob = max(values) if values else 0
        
        return HeatmapResult(
            heatmap_type=heatmap_type,
            grid=grid_array,
            bounds=self.bounds,
            resolution_m=self.config.grid_resolution_m,
            total_cells=total_cells,
            covered_cells=covered_cells,
            coverage_percent=(covered_cells / total_cells * 100) if total_cells > 0 else 0,
            max_probability=max_prob,
            timestamp=0,  # Would be current time
            metadata={
                'search_pattern': self.config.search_pattern,
                'swath_width_m': self.config.swath_width_m
            }
        )
    
    def export_geojson(self, output_path: str, heatmap_type: HeatmapType = HeatmapType.COVERAGE):
        """
        Export heatmap as GeoJSON for GIS display.
        
        Args:
            output_path: Output file path
            heatmap_type: Type of heatmap to export
        """
        features = []
        
        for i in range(self.grid_size[0]):
            for j in range(self.grid_size[1]):
                cell = self.grid.get((i, j))
                if not cell:
                    continue
                
                if heatmap_type == HeatmapType.COVERAGE:
                    value = cell.coverage
                else:
                    value = cell.probability
                
                # Create polygon for cell
                min_lat, min_lon, max_lat, max_lon = self.bounds
                cell_size_lat = (max_lat - min_lat) / self.grid_size[0]
                cell_size_lon = (max_lon - min_lon) / self.grid_size[1]
                
                cell_min_lat = min_lat + i * cell_size_lat
                cell_min_lon = min_lon + j * cell_size_lon
                cell_max_lat = cell_min_lat + cell_size_lat
                cell_max_lon = cell_min_lon + cell_size_lon
                
                feature = {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Polygon',
                        'coordinates': [[
                            [cell_min_lon, cell_min_lat],
                            [cell_max_lon, cell_min_lat],
                            [cell_max_lon, cell_max_lat],
                            [cell_min_lon, cell_max_lat],
                            [cell_min_lon, cell_min_lat]
                        ]]
                    },
                    'properties': {
                        'value': value,
                        'visits': cell.visits,
                        'lat': cell.lat,
                        'lon': cell.lon
                    }
                }
                
                features.append(feature)
        
        geojson = {
            'type': 'FeatureCollection',
            'features': features
        }
        
        with open(output_path, 'w') as f:
            json.dump(geojson, f)
        
        log.info(f"Heatmap exported to {output_path}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get heatmap statistics."""
        total_coverage = sum(cell.coverage for cell in self.grid.values())
        total_probability = sum(cell.probability for cell in self.grid.values())
        
        return {
            'total_cells': len(self.grid),
            'grid_size': self.grid_size,
            'covered_cells': sum(1 for c in self.grid.values() if c.coverage > 0),
            'total_observations': self.total_observations,
            'avg_coverage': total_coverage / max(1, len(self.grid)),
            'avg_probability': total_probability / max(1, len(self.grid)),
            'max_coverage': max((c.coverage for c in self.grid.values()), default=0),
            'max_probability': max((c.probability for c in self.grid.values()), default=0),
            'bounds': self.bounds
        }


# Export
__all__ = ['SARHeatmapGenerator', 'HeatmapType', 'HeatmapConfig', 'HeatmapResult', 'GridCell']