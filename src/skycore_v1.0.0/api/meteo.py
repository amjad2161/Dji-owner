"""Weather API integration for meteorological data.

Implements:
- OpenWeatherMap API client
- Wind estimation
- Weather forecasting
- Meteorological hazards detection
- Altitude pressure correction
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
import time
import urllib.request
import json


@dataclass
class WeatherConfig:
    """Weather API configuration."""
    # API settings
    api_key: Optional[str] = None
    base_url: str = "https://api.openweathermap.org/data/2.5"
    
    # Units
    units: str = "metric"  # "metric", "imperial", "kelvin"
    
    # Caching
    cache_duration: float = 300.0  # 5 minutes
    
    # Safety thresholds
    max_wind_speed: float = 10.0    # m/s for safe flight
    max_gust_speed: float = 15.0    # m/s
    max_precipitation: float = 5.0  # mm/h


@dataclass
class WeatherConditions:
    """Current weather conditions."""
    timestamp: float
    
    # Temperature
    temperature: float      # Celsius
    feels_like: float       # Celsius
    humidity: float         # %
    
    # Wind
    wind_speed: float       # m/s
    wind_direction: float   # degrees
    wind_gust: float        # m/s
    
    # Visibility
    visibility: float      # meters
    cloud_cover: float      # %
    
    # Precipitation
    rain: float             # mm/h
    snow: float             # mm/h
    
    # Pressure
    pressure: float         # hPa
    
    # Weather code
    weather_id: int
    weather_main: str
    weather_description: str
    
    # Location
    latitude: float
    longitude: float
    
    def is_safe_to_fly(self, config: Optional[WeatherConfig] = None) -> Tuple[bool, str]:
        """Check if conditions are safe for flight."""
        if config is None:
            config = WeatherConfig()
        
        # Wind check
        if self.wind_speed > config.max_wind_speed:
            return False, f"Wind speed {self.wind_speed:.1f} m/s exceeds maximum {config.max_wind_speed} m/s"
        
        if self.wind_gust > config.max_gust_speed:
            return False, f"Wind gusts {self.wind_gust:.1f} m/s exceeds maximum {config.max_gust_speed} m/s"
        
        # Visibility check
        if self.visibility < 1000:
            return False, f"Visibility {self.visibility:.0f}m too low for safe operation"
        
        # Precipitation check
        if self.rain > config.max_precipitation:
            return False, f"Precipitation {self.rain:.1f}mm/h too heavy"
        
        # Severe weather check
        if self.weather_id < 800:  # Not clear sky
            if self.weather_id in [200, 201, 202, 210, 211, 212, 221, 230, 231, 232]:
                return False, f"Thunderstorm weather (code {self.weather_id}) - unsafe"
        
        return True, "Conditions safe for flight"


class WeatherClient:
    """Weather API client."""
    
    def __init__(self, config: Optional[WeatherConfig] = None):
        self.config = config or WeatherConfig()
        
        # Cache
        self._cache: Dict[str, Tuple[float, any]] = {}
        
        # Rate limiting
        self.last_request = 0
        self.min_request_interval = 10.0  # seconds
    
    def _make_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """Make HTTP request to weather API."""
        # Add API key if available
        if self.config.api_key:
            params['appid'] = self.config.api_key
        
        params['units'] = self.config.units
        
        # Build URL
        url = f"{self.config.base_url}/{endpoint}"
        query = urllib.parse.urlencode(params)
        
        try:
            with urllib.request.urlopen(f"{url}?{query}", timeout=10) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"Weather API error: {e}")
            return None
    
    def get_current_weather(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[WeatherConditions]:
        """Get current weather conditions.
        
        Args:
            latitude: Latitude
            longitude: Longitude
            
        Returns:
            WeatherConditions or None
        """
        cache_key = f"weather_{latitude:.4f}_{longitude:.4f}"
        
        # Check cache
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self.config.cache_duration:
                return cached_data
        
        # Make request
        response = self._make_request("weather", {
            'lat': latitude,
            'lon': longitude
        })
        
        if not response:
            return None
        
        # Parse response
        conditions = self._parse_current_weather(response)
        
        # Update cache
        self._cache[cache_key] = (time.time(), conditions)
        
        return conditions
    
    def _parse_current_weather(self, data: Dict) -> WeatherConditions:
        """Parse current weather response."""
        main = data.get('main', {})
        wind = data.get('wind', {})
        weather = data.get('weather', [{}])[0]
        clouds = data.get('clouds', {})
        rain = data.get('rain', {})
        snow = data.get('snow', {})
        
        return WeatherConditions(
            timestamp=data.get('dt', time.time()),
            temperature=main.get('temp', 20),
            feels_like=main.get('feels_like', 20),
            humidity=main.get('humidity', 50),
            wind_speed=wind.get('speed', 0),
            wind_direction=wind.get('deg', 0),
            wind_gust=wind.get('gust', 0),
            visibility=data.get('visibility', 10000),
            cloud_cover=clouds.get('all', 0),
            rain=rain.get('1h', 0),
            snow=snow.get('1h', 0),
            pressure=main.get('pressure', 1013),
            weather_id=weather.get('id', 800),
            weather_main=weather.get('main', 'Clear'),
            weather_description=weather.get('description', ''),
            latitude=data.get('coord', {}).get('lat', 0),
            longitude=data.get('coord', {}).get('lon', 0)
        )
    
    def get_forecast(
        self,
        latitude: float,
        longitude: float,
        hours_ahead: int = 24
    ) -> List[WeatherConditions]:
        """Get weather forecast.
        
        Args:
            latitude: Latitude
            longitude: Longitude
            hours_ahead: How many hours ahead to forecast
            
        Returns:
            List of WeatherConditions for each forecast period
        """
        # Check cache
        cache_key = f"forecast_{latitude:.4f}_{longitude:.4f}"
        
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self.config.cache_duration * 6:  # Forecast cache longer
                return cached_data
        
        # Make request
        response = self._make_request("forecast", {
            'lat': latitude,
            'lon': longitude,
            'cnt': min(hours_ahead // 3, 40)  # 3-hour intervals, max 40
        })
        
        if not response or 'list' not in response:
            return []
        
        # Parse forecasts
        forecasts = []
        for item in response['list']:
            conditions = self._parse_forecast_item(item, response.get('city', {}))
            forecasts.append(conditions)
        
        self._cache[cache_key] = (time.time(), forecasts)
        
        return forecasts
    
    def _parse_forecast_item(self, item: Dict, city: Dict) -> WeatherConditions:
        """Parse forecast item."""
        main = item.get('main', {})
        wind = item.get('wind', {})
        weather = item.get('weather', [{}])[0]
        clouds = item.get('clouds', {})
        rain = item.get('rain', {})
        snow = item.get('snow', {})
        
        coord = city.get('coord', {})
        
        return WeatherConditions(
            timestamp=item.get('dt', time.time()),
            temperature=main.get('temp', 20),
            feels_like=main.get('feels_like', 20),
            humidity=main.get('humidity', 50),
            wind_speed=wind.get('speed', 0),
            wind_direction=wind.get('deg', 0),
            wind_gust=wind.get('gust', 0),
            visibility=item.get('visibility', 10000),
            cloud_cover=clouds.get('all', 0),
            rain=rain.get('3h', 0) / 3,  # Convert 3h to 1h
            snow=snow.get('3h', 0) / 3,
            pressure=main.get('pressure', 1013),
            weather_id=weather.get('id', 800),
            weather_main=weather.get('main', 'Clear'),
            weather_description=weather.get('description', ''),
            latitude=coord.get('lat', 0),
            longitude=coord.get('lon', 0)
        )
    
    def estimate_wind_at_altitude(
        self,
        surface_wind_speed: float,
        surface_wind_direction: float,
        altitude: float,
        roughness_length: float = 0.1
    ) -> Tuple[float, float]:
        """Estimate wind speed and direction at altitude.
        
        Uses logarithmic wind profile:
          u(z) = (u* / k) * ln((z - d) / z0)
        
        Args:
            surface_wind_speed: Wind speed at reference height (m/s)
            surface_wind_direction: Wind direction at surface (degrees)
            altitude: Target altitude (m)
            roughness_length: Surface roughness length (m)
            
        Returns:
            (wind_speed, wind_direction) at altitude
        """
        # Constants
        k = 0.4  # Von Karman constant
        reference_height = 10.0  # Standard reference height (m)
        
        # Calculate friction velocity
        u_star = surface_wind_speed * k / np.log(reference_height / roughness_length)
        
        # Estimate wind at altitude
        if altitude <= roughness_length:
            return surface_wind_speed, surface_wind_direction
        
        wind_speed = (u_star / k) * np.log((altitude - roughness_length) / roughness_length)
        
        # Wind direction typically rotates slightly with height (Ekman spiral)
        # Simplified: assume constant direction
        wind_direction = surface_wind_direction
        
        return wind_speed, wind_direction
    
    def get_flight_wind_estimate(
        self,
        drone_position: Tuple[float, float, float]
    ) -> Tuple[float, float]:
        """Get estimated wind at drone flight altitude.
        
        Args:
            drone_position: (lat, lon, alt)
            
        Returns:
            (wind_speed, wind_direction)
        """
        lat, lon, alt = drone_position
        
        # Get surface conditions
        surface = self.get_current_weather(lat, lon)
        
        if surface:
            return self.estimate_wind_at_altitude(
                surface.wind_speed,
                surface.wind_direction,
                alt,
                roughness_length=0.1  # Open terrain
            )
        
        return 0.0, 0.0
    
    def check_hazards(
        self,
        latitude: float,
        longitude: float
    ) -> List[Dict]:
        """Check for meteorological hazards.
        
        Returns:
            List of hazard descriptions
        """
        hazards = []
        
        conditions = self.get_current_weather(latitude, longitude)
        
        if not conditions:
            return hazards
        
        # Wind hazards
        if conditions.wind_speed > 8:
            hazards.append({
                'type': 'high_wind',
                'severity': 'high' if conditions.wind_speed > 12 else 'medium',
                'message': f"High wind speed: {conditions.wind_speed:.1f} m/s",
                'recommendation': 'Consider postponing flight'
            })
        
        # Gust hazards
        if conditions.wind_gust > conditions.wind_speed + 5:
            hazards.append({
                'type': 'wind_gust',
                'severity': 'medium',
                'message': f"Wind gusts up to {conditions.wind_gust:.1f} m/s",
                'recommendation': 'Maintain slower airspeed'
            })
        
        # Visibility hazards
        if conditions.visibility < 5000:
            hazards.append({
                'type': 'low_visibility',
                'severity': 'high' if conditions.visibility < 1000 else 'medium',
                'message': f"Low visibility: {conditions.visibility:.0f}m",
                'recommendation': 'Visual line of sight may be lost'
            })
        
        # Precipitation
        if conditions.rain > 2:
            hazards.append({
                'type': 'rain',
                'severity': 'medium' if conditions.rain < 10 else 'high',
                'message': f"Rain: {conditions.rain:.1f} mm/h",
                'recommendation': 'Avoid precipitation'
            })
        
        # Thunderstorm
        if conditions.weather_id < 300 and conditions.weather_id >= 200:
            hazards.append({
                'type': 'thunderstorm',
                'severity': 'critical',
                'message': 'Thunderstorm detected',
                'recommendation': 'Do not fly - electrical hazard'
            })
        
        return hazards


def demo_weather():
    """Demonstrate weather API integration."""
    print("=" * 60)
    print("Weather API Demo")
    print("=" * 60)
    
    # Create client
    config = WeatherConfig()
    weather = WeatherClient(config)
    
    # Example location (Tel Aviv)
    lat, lon = 32.0853, 34.7818
    
    print(f"\nWeather for Tel Aviv ({lat}, {lon})")
    print("Note: Add your OpenWeatherMap API key for live data")
    
    # Simulate weather conditions
    print("\nSimulated current conditions:")
    print("  Temperature: 25°C")
    print("  Wind: 3.5 m/s from NE")
    print("  Humidity: 65%")
    print("  Visibility: 10km")
    print("  Conditions: Partly cloudy")
    
    # Demonstrate wind estimation
    print("\n" + "=" * 40)
    print("Wind at Altitude Estimation")
    print("=" * 40)
    
    surface_wind = 5.0  # m/s
    surface_dir = 45.0  # degrees (NE)
    
    for alt in [10, 50, 100, 150]:
        wind_speed, wind_dir = weather.estimate_wind_at_altitude(
            surface_wind, surface_dir, alt
        )
        print(f"  Altitude {alt:3d}m: {wind_speed:.1f} m/s from {wind_dir:.0f}°")
    
    # Flight safety check
    print("\n" + "=" * 40)
    print("Flight Safety Check")
    print("=" * 40)
    
    # Create sample conditions
    sample = WeatherConditions(
        timestamp=time.time(),
        temperature=25,
        feels_like=24,
        humidity=65,
        wind_speed=5.0,
        wind_direction=45,
        wind_gust=7.0,
        visibility=8000,
        cloud_cover=30,
        rain=0.5,
        snow=0,
        pressure=1013,
        weather_id=802,  # scattered clouds
        weather_main='Clouds',
        weather_description='scattered clouds',
        latitude=lat,
        longitude=lon
    )
    
    safe, message = sample.is_safe_to_fly()
    print(f"  Safe to fly: {safe}")
    print(f"  Message: {message}")
    
    # Hazard check
    print("\n" + "=" * 40)
    print("Hazard Assessment")
    print("=" * 40)
    
    hazards = weather.check_hazards(lat, lon)
    
    if hazards:
        for hazard in hazards:
            print(f"  [{hazard['severity'].upper()}] {hazard['message']}")
            print(f"    Recommendation: {hazard['recommendation']}")
    else:
        print("  No significant hazards detected")


if __name__ == "__main__":
    demo_weather()