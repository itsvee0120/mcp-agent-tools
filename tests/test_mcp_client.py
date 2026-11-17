"""Test 4: client-server communication and dynamic tool discovery."""

import json

import pytest

from src.client.mcp_client import MCPClient

EXPECTED_TOOLS = {
    "query_sql_database": "sql_query",
    "get_live_weather": "city",
    "evaluate_math_expression": "expression",
}


@pytest.mark.asyncio
async def test_dynamic_tool_discovery():
    """Test 4: the client connects over stdio and discovers all 3 tools with valid schemas."""
    async with MCPClient() as client:
        tools = await client.list_tools()
        openai_tools = await client.get_openai_tools()
        math_result = json.loads(
            await client.call_tool("evaluate_math_expression", {"expression": "2 + 2"})
        )
        unknown = await client.call_tool("does_not_exist", {})

    assert {t.name for t in tools} == set(EXPECTED_TOOLS)
    for tool in tools:
        param = EXPECTED_TOOLS[tool.name]
        assert tool.description
        assert tool.input_schema["type"] == "object"
        assert tool.input_schema["properties"][param]["type"] == "string"
        assert param in tool.input_schema["required"]

    for entry in openai_tools:
        assert entry["type"] == "function"
        assert set(entry["function"]) == {"name", "description", "parameters"}
        assert entry["function"]["name"] in EXPECTED_TOOLS
        assert entry["function"]["parameters"]["type"] == "object"

    assert math_result["result"] == 4
    assert unknown.startswith("Error: unknown tool")
