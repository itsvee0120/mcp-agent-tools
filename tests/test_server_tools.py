"""Tests 1-3: individual tool execution."""

import json

import httpx
import pytest

from src.server.mcp_server import evaluate_math_expression, query_sql_database
from src.server.tools.weather_tool import FORECAST_URL, GEOCODE_URL, get_weather


def test_sql_read_accuracy():
    """Test 1: a valid SELECT returns the expected columns and row values."""
    result = json.loads(
        query_sql_database(
            "SELECT order_id, sku, quantity, order_value FROM orders WHERE order_id = 4492"
        )
    )
    assert result["columns"] == ["order_id", "sku", "quantity", "order_value"]
    assert result["rows"] == [[4492, "SKU-90210", 120, 10740.0]]
    assert result["row_count"] == 1

    stock = json.loads(
        query_sql_database(
            "SELECT quantity FROM inventory WHERE sku = 'SKU-90210' AND warehouse_city = 'Seattle'"
        )
    )
    assert stock["rows"] == [[150]]


def _mock_open_meteo(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url.startswith(GEOCODE_URL):
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "name": "Seattle",
                        "admin1": "Washington",
                        "country": "United States",
                        "latitude": 47.6062,
                        "longitude": -122.3321,
                    }
                ]
            },
        )
    if url.startswith(FORECAST_URL):
        return httpx.Response(
            200,
            json={
                "current": {
                    "temperature_2m": 9.4,
                    "precipitation": 1.2,
                    "rain": 1.2,
                    "weather_code": 63,
                    "wind_speed_10m": 14.8,
                },
                "daily": {
                    "precipitation_sum": [8.5],
                    "precipitation_probability_max": [90],
                },
            },
        )
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_weather_api_integration():
    """Test 2: mocked Open-Meteo responses are formatted into the expected summary."""
    async with httpx.AsyncClient(transport=httpx.MockTransport(_mock_open_meteo)) as client:
        result = json.loads(await get_weather("  seattle, WA ", client=client))

    assert result["location"] == {
        "name": "Seattle",
        "region": "Washington",
        "country": "United States",
        "latitude": 47.6062,
        "longitude": -122.3321,
    }
    assert result["current"] == {
        "temperature_c": 9.4,
        "conditions": "Moderate rain",
        "precipitation_mm": 1.2,
        "rain_mm": 1.2,
        "wind_speed_kmh": 14.8,
    }
    assert result["today"] == {
        "precipitation_sum_mm": 8.5,
        "precipitation_probability_max_pct": 90.0,
    }


def test_math_evaluator_precision():
    """Test 3: order of operations is evaluated correctly."""
    assert json.loads(evaluate_math_expression("2 + 3 * (4 - 1) ** 2"))["result"] == 29
    assert json.loads(evaluate_math_expression("10740 * 0.035"))["result"] == 375.9
