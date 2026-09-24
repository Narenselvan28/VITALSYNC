"""
VITALSYNC: Weather Context Module
Provides external meteorological and environmental exposure context derived from GPS NEO-7.
Enforces offline-first local sensor fallback and ensures weather remains purely contextual.
"""

from backend.core.weather_service import (
    WeatherContextEngine,
    WeatherProvider,
    CachedOpenMeteoProvider,
    get_weather_engine,
)

# Export standard getter
def get_weather_context_engine() -> WeatherContextEngine:
    return get_weather_engine()
