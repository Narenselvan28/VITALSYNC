"""
VITALSYNC: Weather Intelligence & External Environmental Context
Integrates GPS NEO-7 coordinates with regional weather and air-quality context.
Enforces that external weather is CONTEXTUAL ONLY and never directly creates a health alert.
Provides an offline-first architecture with caching and graceful LOCAL SENSOR MODE fallback.
"""

import time
import requests
from typing import Dict, Any, Optional

class WeatherProvider:
    """Abstract interface for weather providers."""
    def get_weather(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

class CachedOpenMeteoProvider(WeatherProvider):
    """
    Open-Meteo REST provider (free, non-commercial, no API key required).
    Maintains a 30-minute in-memory cache to minimize network calls and operate on edge.
    """
    def __init__(self, cache_ttl_seconds: int = 1800):
        self.cache_ttl = cache_ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.offline_mode = False

    def get_weather(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        if self.offline_mode:
            return None

        # Round coordinates to ~1 km grid for efficient caching
        cache_key = f"{round(lat, 2)},{round(lon, 2)}"
        now = time.time()

        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if (now - entry["cached_at"]) < self.cache_ttl:
                data = dict(entry["data"])
                data["is_cached"] = True
                return data

        try:
            # Query Open-Meteo API with timeout for edge safety
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&current="
                f"temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,surface_pressure,wind_speed_10m"
            )
            resp = requests.get(url, timeout=2.5)
            if resp.status_code == 200:
                current = resp.json().get("current", {})
                temp = float(current.get("temperature_2m", 28.0))
                humidity = float(current.get("relative_humidity_2m", 60.0))
                apparent = float(current.get("apparent_temperature", temp))
                wind = float(current.get("wind_speed_10m", 3.0))
                pressure = float(current.get("surface_pressure", 1013.2))
                precip = float(current.get("precipitation", 0.0))

                # Compute regional heat index approximation
                heat_idx = apparent if apparent > temp else temp

                # Identify potential extreme weather warnings
                warning = "NONE"
                if temp > 40.0 or apparent > 44.0:
                    warning = "EXTREME_HEAT_WARNING"
                elif wind > 50.0:
                    warning = "HIGH_WIND_ADVISORY"
                elif precip > 25.0:
                    warning = "HEAVY_RAIN_WARNING"

                weather_data = {
                    "source": "Open-Meteo",
                    "latitude": lat,
                    "longitude": lon,
                    "outdoor_temperature": temp,
                    "apparent_temperature": apparent,
                    "humidity": humidity,
                    "wind_speed": wind,
                    "pressure": pressure,
                    "precipitation": precip,
                    "heat_index": round(heat_idx, 1),
                    "weather_warning": warning,
                    "status": "ONLINE",
                    "is_cached": False,
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }

                self.cache[cache_key] = {"data": weather_data, "cached_at": now}
                return weather_data
        except Exception:
            # On network timeout or failure, return None to trigger LOCAL SENSOR MODE
            pass

        return None

class WeatherContextEngine:
    def __init__(self):
        self.provider = CachedOpenMeteoProvider()
        self.forced_offline = False
        self.override_data: Optional[Dict[str, Any]] = None

    def set_forced_offline(self, offline: bool):
        self.forced_offline = offline
        self.provider.offline_mode = offline

    def set_mock_weather(self, weather_override: Optional[Dict[str, Any]]):
        self.override_data = weather_override

    def get_context(self, lat: Optional[float], lon: Optional[float]) -> Dict[str, Any]:
        """
        Retrieves current environmental context based on GPS coordinates.
        Never crashes when GPS or internet is absent; smoothly degrades to LOCAL SENSOR MODE.
        """
        if self.override_data:
            res = dict(self.override_data)
            res["status"] = "MOCK_ACTIVE"
            return res

        if self.forced_offline or lat is None or lon is None or (lat == 0.0 and lon == 0.0):
            return {
                "status": "OFFLINE",
                "mode": "LOCAL_SENSOR_MODE",
                "message": "External weather service offline. Operating on 100% local onboard sensors.",
                "outdoor_temperature": None,
                "apparent_temperature": None,
                "humidity": None,
                "heat_index": None,
                "weather_warning": "NONE",
                "thermal_context_weight": 0.0,
            }

        weather = self.provider.get_weather(lat, lon)
        if not weather:
            return {
                "status": "OFFLINE",
                "mode": "LOCAL_SENSOR_MODE",
                "message": "External weather network unreachable. Operating in local sensor mode.",
                "outdoor_temperature": None,
                "apparent_temperature": None,
                "humidity": None,
                "heat_index": None,
                "weather_warning": "NONE",
                "thermal_context_weight": 0.0,
            }

        # Calculate contextual influence (bounded to context layer only)
        # For example, high outdoor heat (>36°C) adds +0.05 to +0.12 contextual strain weight
        outdoor_t = weather["outdoor_temperature"]
        heat_idx = weather["heat_index"]
        context_weight = 0.0
        if heat_idx > 40.0:
            context_weight = 0.12
        elif heat_idx > 35.0:
            context_weight = 0.06

        return {
            "status": "ONLINE",
            "mode": "WEATHER_AUGMENTED",
            "message": f"External weather connected ({weather['outdoor_temperature']}°C, Feels like {weather['apparent_temperature']}°C).",
            "outdoor_temperature": weather["outdoor_temperature"],
            "apparent_temperature": weather["apparent_temperature"],
            "humidity": weather["humidity"],
            "wind_speed": weather.get("wind_speed", 0.0),
            "heat_index": weather["heat_index"],
            "weather_warning": weather["weather_warning"],
            "thermal_context_weight": context_weight,
            "is_cached": weather.get("is_cached", False),
            "source": weather.get("source", "Open-Meteo"),
        }

_weather_engine = WeatherContextEngine()

def get_weather_engine() -> WeatherContextEngine:
    return _weather_engine
