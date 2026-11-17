"""Live weather via Open-Meteo (geocoding + forecast). No API key needed.

- Async httpx client with request timeout and an overall timeout.
- City input is normalized and validated before use.
- 429 rate limits are retried once, then reported.
- API output is sanitized: only whitelisted numeric fields and cleaned
  place names are returned, never raw API text.
"""

import asyncio
import json
import math
import re

import httpx

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SECONDS = 10.0
TOTAL_TIMEOUT_SECONDS = 20.0
MAX_CITY_LENGTH = 80
RATE_LIMIT_RETRY_SECONDS = 2.0

_CITY_ALLOWED_RE = re.compile(r"^[^\W\d_]+(?:[ '.\-]{1,2}[^\W\d_]+)*\.?$")
_SAFE_TEXT_RE = re.compile(r"[^\w '.,\-]")

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


class WeatherError(Exception):
    """Raised for invalid input or unusable API responses."""


def normalize_city(city: str) -> str:
    """Trim, collapse whitespace, drop any ', region' suffix, and validate."""
    if not isinstance(city, str):
        raise WeatherError("City must be a string.")
    name = " ".join(city.split(",")[0].split())
    if not name:
        raise WeatherError("City must not be empty.")
    if len(name) > MAX_CITY_LENGTH:
        raise WeatherError(f"City exceeds {MAX_CITY_LENGTH} characters.")
    if not _CITY_ALLOWED_RE.match(name):
        raise WeatherError("City contains invalid characters.")
    return name


def _clean_text(value, max_len: int = 80) -> str | None:
    """Keep only plain characters from API-provided text."""
    if not isinstance(value, str):
        return None
    return _SAFE_TEXT_RE.sub("", value)[:max_len].strip() or None


def _num(value) -> float | None:
    """Return a finite float or None (drops anything non-numeric)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _first(values) -> float | None:
    return _num(values[0]) if isinstance(values, list) and values else None


async def _get_json(client: httpx.AsyncClient, url: str, params: dict) -> dict:
    """GET JSON, retrying once on HTTP 429."""
    for attempt in range(2):
        response = await client.get(url, params=params)
        if response.status_code == 429:
            if attempt == 0:
                await asyncio.sleep(RATE_LIMIT_RETRY_SECONDS)
                continue
            raise WeatherError("Weather API rate limit reached. Try again later.")
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise WeatherError("Unexpected response from weather API.")
        return data
    raise WeatherError("Weather API request failed.")


async def _fetch_weather(city: str, client: httpx.AsyncClient) -> dict:
    geo = await _get_json(
        client, GEOCODE_URL, {"name": city, "count": 1, "language": "en", "format": "json"}
    )
    results = geo.get("results")
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        raise WeatherError(f"City not found: {city}")
    place = results[0]
    lat, lon = _num(place.get("latitude")), _num(place.get("longitude"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise WeatherError("Geocoding returned invalid coordinates.")

    forecast = await _get_json(
        client,
        FORECAST_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,precipitation,rain,weather_code,wind_speed_10m",
            "daily": "precipitation_sum,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": 1,
        },
    )
    current = forecast.get("current")
    if not isinstance(current, dict):
        raise WeatherError("Forecast response missing current conditions.")
    daily = forecast.get("daily") if isinstance(forecast.get("daily"), dict) else {}

    code = _num(current.get("weather_code"))
    return {
        "location": {
            "name": _clean_text(place.get("name")),
            "region": _clean_text(place.get("admin1")),
            "country": _clean_text(place.get("country")),
            "latitude": lat,
            "longitude": lon,
        },
        "current": {
            "temperature_c": _num(current.get("temperature_2m")),
            "conditions": WMO_CODES.get(int(code), "Unknown") if code is not None else "Unknown",
            "precipitation_mm": _num(current.get("precipitation")),
            "rain_mm": _num(current.get("rain")),
            "wind_speed_kmh": _num(current.get("wind_speed_10m")),
        },
        "today": {
            "precipitation_sum_mm": _first(daily.get("precipitation_sum")),
            "precipitation_probability_max_pct": _first(daily.get("precipitation_probability_max")),
        },
    }


def _error(error_type: str, message: str) -> str:
    return json.dumps({"error": {"type": error_type, "message": message}})


async def get_weather(city: str, client: httpx.AsyncClient | None = None) -> str:
    """Return current weather for a city as a JSON string (never raises).

    Pass ``client`` to inject a custom/mocked httpx.AsyncClient (used in tests).
    """
    try:
        name = normalize_city(city)
        if client is not None:
            data = await asyncio.wait_for(_fetch_weather(name, client), TOTAL_TIMEOUT_SECONDS)
        else:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as own_client:
                data = await asyncio.wait_for(
                    _fetch_weather(name, own_client), TOTAL_TIMEOUT_SECONDS
                )
        return json.dumps(data)
    except WeatherError as exc:
        return _error("WeatherError", str(exc))
    except (asyncio.TimeoutError, httpx.TimeoutException):
        return _error("TimeoutError", "Weather API request timed out.")
    except httpx.HTTPStatusError as exc:
        return _error("HTTPError", f"Weather API returned HTTP {exc.response.status_code}.")
    except httpx.RequestError:
        return _error("NetworkError", "Could not reach weather API.")
    except ValueError:
        return _error("ParseError", "Weather API returned invalid JSON.")
    except Exception as exc:  # never crash the server
        return _error(type(exc).__name__, "Unexpected error while fetching weather.")
