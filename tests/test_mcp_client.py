"""Tests 4-5: client-server communication, discovery, and the agent loop."""

import json
from types import SimpleNamespace

import pytest

from src.client.agent_loop import run_agent
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
        anthropic_tools = await client.get_anthropic_tools()
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

    for entry in anthropic_tools:
        assert set(entry) == {"name", "description", "input_schema"}
        assert entry["name"] in EXPECTED_TOOLS
        assert entry["input_schema"]["type"] == "object"

    assert math_result["result"] == 4
    assert unknown.startswith("Error: unknown tool")


def _tool_use(block_id: str, name: str, arguments: dict) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=arguments)


class _ScriptedLLM:
    """Fake Anthropic client: returns scripted responses, records each request."""

    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = iter(responses)
        self.requests: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return next(self._responses)


@pytest.mark.asyncio
async def test_multi_step_chained_loop():
    """Test 5: SQL lookup then Math evaluation; loop ends with an assistant answer within 3 turns."""
    llm = _ScriptedLLM(
        [
            SimpleNamespace(
                stop_reason="tool_use",
                content=[
                    _tool_use(
                        "toolu_1",
                        "query_sql_database",
                        {"sql_query": "SELECT order_value FROM orders WHERE order_id = 4492"},
                    )
                ],
            ),
            SimpleNamespace(
                stop_reason="tool_use",
                content=[
                    _tool_use("toolu_2", "evaluate_math_expression", {"expression": "10740 * 0.035"})
                ],
            ),
            SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text="Insurance for order #4492 is $375.90.")],
            ),
        ]
    )

    async with MCPClient() as client:
        result = await run_agent(
            "What is 3.5% shipping insurance on order #4492?", client, llm_client=llm
        )

    assert result.turns <= 3
    assert result.stop_reason == "end_turn"
    assert result.messages[-1]["role"] == "assistant"
    assert result.final_text == "Insurance for order #4492 is $375.90."

    assert [c.name for c in result.tool_calls] == ["query_sql_database", "evaluate_math_expression"]
    assert json.loads(result.tool_calls[0].result)["rows"] == [[10740.0]]
    assert json.loads(result.tool_calls[1].result)["result"] == 375.9
    assert not any(c.is_error for c in result.tool_calls)

    # Each tool result was sent back with the matching tool_use_id.
    for request, expected_id in zip(llm.requests[1:], ["toolu_1", "toolu_2"]):
        tool_result = request["messages"][-1]["content"][0]
        assert tool_result["type"] == "tool_result"
        assert tool_result["tool_use_id"] == expected_id

    # Tools were discovered from the server, not hardcoded.
    assert {t["name"] for t in llm.requests[0]["tools"]} == {
        "query_sql_database",
        "get_live_weather",
        "evaluate_math_expression",
    }
