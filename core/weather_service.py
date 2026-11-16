"""
Live Weather Intelligence Service for Operation JARVIS.
Integrates Open-Meteo Geocoding and Weather Forecast APIs (free, no API key required).
Provides authoritative, real-time meteorological observations, feels-like temperatures,
humidity, wind speed, rain probability, and multi-day forecasts with strict temporal grounding.
"""
import json
import logging
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, Optional
from core.temporal import get_system_temporal_info

logger = logging.getLogger("jarvis.weather")

WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}

DEFAULT_LOCATION = {
    "name": "Bengaluru",
    "region": "Karnataka",
    "country": "India",
    "latitude": 12.97194,
    "longitude": 77.59369,
    "timezone": "Asia/Kolkata"
}

_CACHE_TTL_SECONDS = 600.0  # 10 minutes cache
_WEATHER_CACHE: Dict[str, Dict[str, Any]] = {}

def geocode_location(location_name: Optional[str] = None, timeout: float = 5.0) -> Dict[str, Any]:
    """
    Resolves explicit location name to coordinates and timezone.
    If no location is supplied or refers to local environment, defaults to user's
    established location (Bengaluru, Karnataka, India).
    """
    if not location_name or location_name.strip().lower() in ("here", "current", "outside", "local", "my location", "today", "tomorrow"):
        return {"ok": True, "location": DEFAULT_LOCATION, "is_default": True}

    clean_loc = location_name.strip()
    encoded = urllib.parse.quote(clean_loc)
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded}&count=1&language=en&format=json"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "OperationJARVIS/2.0 (Local-First AI Orchestrator)"}
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results")
            if not results:
                return {
                    "ok": False,
                    "error": f"Location '{clean_loc}' could not be resolved by geocoding service.",
                    "is_default": False
                }
            top = results[0]
            loc_data = {
                "name": top.get("name", clean_loc),
                "region": top.get("admin1", ""),
                "country": top.get("country", ""),
                "latitude": top.get("latitude"),
                "longitude": top.get("longitude"),
                "timezone": top.get("timezone", "Asia/Kolkata")
            }
            return {"ok": True, "location": loc_data, "is_default": False}
    except urllib.error.URLError as e:
        logger.warning(f"Geocoding network error for '{clean_loc}': {e}")
        return {"ok": False, "error": f"Geocoding network error: {e}", "is_default": False}
    except Exception as e:
        logger.warning(f"Geocoding exception for '{clean_loc}': {e}")
        return {"ok": False, "error": f"Geocoding failed: {str(e)}", "is_default": False}

def get_weather(
    location: Optional[str] = None,
    force_refresh: bool = False,
    timeout: float = 5.0
) -> Dict[str, Any]:
    """
    Retrieves live or cached weather observations and forecasts from Open-Meteo.
    Grounds all metrics in authoritative Windows host temporal timestamps.
    Never fabricates values on provider failure.
    """
    temporal_info = get_system_temporal_info()
    host_time_iso = temporal_info.get("iso_timestamp", datetime.now().isoformat())
    host_time_str = temporal_info.get("formatted", datetime.now().strftime("%I:%M %p"))

    geo_res = geocode_location(location, timeout=timeout)
    if not geo_res.get("ok"):
        return {
            "ok": False,
            "error": geo_res.get("error", "Failed to resolve location."),
            "retrieval_time": host_time_iso,
            "summary": f"Could not retrieve weather: {geo_res.get('error')}"
        }

    loc = geo_res["location"]
    cache_key = f"{loc['latitude']:.4f}_{loc['longitude']:.4f}"
    now_ts = time.time()

    if not force_refresh and cache_key in _WEATHER_CACHE:
        entry = _WEATHER_CACHE[cache_key]
        if (now_ts - entry["cached_timestamp"]) < _CACHE_TTL_SECONDS:
            res = dict(entry["data"])
            res["is_cached"] = True
            res["cached_at"] = entry["cached_time_str"]
            res["provenance"] = f"[Cached observation from {entry['cached_time_str']}]"
            res["summary"] = f"[Cached: {entry['cached_time_str']}] {res.get('summary', '')}"
            return res

    lat = loc["latitude"]
    lon = loc["longitude"]
    tz = loc.get("timezone", "auto")

    forecast_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max"
        f"&timezone={urllib.parse.quote(tz)}"
    )

    req = urllib.request.Request(
        forecast_url,
        headers={"User-Agent": "OperationJARVIS/2.0 (Local-First AI Orchestrator)"}
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        logger.error(f"Weather API request error: {e}")
        return {
            "ok": False,
            "error": f"Weather provider unreachable: {e}",
            "retrieval_time": host_time_iso,
            "summary": f"Weather provider network failure: {e}"
        }
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        return {
            "ok": False,
            "error": f"Weather provider error: {str(e)}",
            "retrieval_time": host_time_iso,
            "summary": f"Weather provider failure: {str(e)}"
        }

    current = data.get("current")
    daily = data.get("daily")

    if not current or not daily:
        return {
            "ok": False,
            "error": "Weather provider returned empty or malformed payload.",
            "retrieval_time": host_time_iso,
            "summary": "Weather provider returned invalid data."
        }

    w_code = current.get("weather_code", 0)
    w_condition = WMO_WEATHER_CODES.get(w_code, "Unknown")
    temp = current.get("temperature_2m")
    feels_like = current.get("apparent_temperature", temp)
    humidity = current.get("relative_humidity_2m")
    wind_speed = current.get("wind_speed_10m")
    precip = current.get("precipitation", 0.0)
    obs_time = current.get("time", "")

    # Daily forecasts
    dates = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    daily_codes = daily.get("weather_code", [])
    rain_probs = daily.get("precipitation_probability_max", [])

    today_forecast = {}
    if len(dates) > 0:
        today_forecast = {
            "date": dates[0],
            "condition": WMO_WEATHER_CODES.get(daily_codes[0] if len(daily_codes) > 0 else 0, "Unknown"),
            "max_temp_c": max_temps[0] if len(max_temps) > 0 else None,
            "min_temp_c": min_temps[0] if len(min_temps) > 0 else None,
            "rain_probability_pct": rain_probs[0] if len(rain_probs) > 0 else 0
        }

    tomorrow_forecast = {}
    if len(dates) > 1:
        tomorrow_forecast = {
            "date": dates[1],
            "condition": WMO_WEATHER_CODES.get(daily_codes[1] if len(daily_codes) > 1 else 0, "Unknown"),
            "max_temp_c": max_temps[1] if len(max_temps) > 1 else None,
            "min_temp_c": min_temps[1] if len(min_temps) > 1 else None,
            "rain_probability_pct": rain_probs[1] if len(rain_probs) > 1 else 0
        }

    loc_label = loc["name"]
    if loc.get("region") and loc["region"] != loc["name"]:
        loc_label += f", {loc['region']}"
    if loc.get("country"):
        loc_label += f", {loc['country']}"

    summary = (
        f"Currently in {loc_label}, it's {temp}°C (feels like {feels_like}°C) with {w_condition.lower()} conditions. "
        f"Humidity is {humidity}%, with a wind speed of {wind_speed} km/h. "
        f"Precipitation is {precip} mm (rain probability today is {today_forecast.get('rain_probability_pct', 0)}%). "
        f"These are the latest available observations retrieved at {host_time_str}."
    )

    result_payload = {
        "ok": True,
        "is_cached": False,
        "provenance": f"[Live observation retrieved at {host_time_str}]",
        "location": loc,
        "location_display": loc_label,
        "current": {
            "temperature_c": temp,
            "apparent_temperature_c": feels_like,
            "condition": w_condition,
            "weather_code": w_code,
            "humidity_pct": humidity,
            "wind_speed_kmh": wind_speed,
            "precipitation_mm": precip,
            "rain_probability_pct": today_forecast.get("rain_probability_pct", 0),
            "observation_time": obs_time
        },
        "today_forecast": today_forecast,
        "tomorrow_forecast": tomorrow_forecast,
        "retrieval_time": host_time_iso,
        "summary": summary
    }

    # Update cache
    _WEATHER_CACHE[cache_key] = {
        "cached_timestamp": now_ts,
        "cached_time_str": host_time_str,
        "data": result_payload
    }

    return result_payload
