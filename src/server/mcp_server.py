"""MCP server exposing three sandboxed tools over stdio.

Uses the official MCP Python SDK. In mcp 2.x, ``FastMCP`` was renamed to
``MCPServer`` (same decorator API).

Run: uv run python -m src.server.mcp_server
"""

from mcp.server.mcpserver import MCPServer

from src.server.tools.math_tool import calculate
from src.server.tools.sql_tool import run_query
from src.server.tools.weather_tool import get_weather

mcp = MCPServer(
    name="enterprise-ops-tools",
    instructions=(
        "Tools for an enterprise logistics assistant: read-only SQL over the "
        "operations database, live weather, and safe math evaluation."
    ),
)


@mcp.tool(structured_output=False)
def query_sql_database(sql_query: str) -> str:
    """Run a single read-only SQL SELECT on the enterprise operations SQLite database.

    Tables:
    - customers(customer_id, name, city)
    - products(sku, name, unit_price)
    - inventory(inventory_id, sku, warehouse_city, quantity)
    - orders(order_id, customer_id, sku, quantity, order_value, status, order_date)

    Only one SELECT statement is allowed: no comments, no ';' stacking, no
    INSERT/UPDATE/DELETE/DROP/ATTACH/PRAGMA. Returns JSON with columns and rows
    (max 100), or a JSON error.
    """
    return run_query(sql_query)


@mcp.tool(structured_output=False)
async def get_live_weather(city: str) -> str:
    """Get current weather and today's precipitation for a city (Open-Meteo).

    Pass a plain city name, e.g. "Seattle". Returns JSON with location,
    temperature (C), conditions, precipitation/rain (mm), wind speed (km/h), and
    today's precipitation total and max probability, or a JSON error.
    """
    return await get_weather(city)


@mcp.tool(structured_output=False)
def evaluate_math_expression(expression: str) -> str:
    """Evaluate an arithmetic expression exactly, without guessing.

    Supports + - * / // % **, parentheses, numbers, the constants pi and e, and
    the functions sqrt, log, log10, exp, sin, cos, tan, abs, round, floor, ceil.
    Example: "10740 * 0.035". Returns JSON with the result, or a JSON error.
    """
    return calculate(expression)


if __name__ == "__main__":
    mcp.run(transport="stdio")
