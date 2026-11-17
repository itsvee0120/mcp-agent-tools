"""MCP client: launches the server over stdio, discovers tools, calls them.

Tools are always discovered via ``session.list_tools()`` (never hardcoded) and
mapped from MCP ``inputSchema`` to Anthropic Messages API tool definitions.
"""

import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp import types

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOL_CALL_TIMEOUT_SECONDS = 30.0


def default_server_params() -> StdioServerParameters:
    """Spawn the project's MCP server as a child process using the current Python."""
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.server.mcp_server"],
        cwd=PROJECT_ROOT,
    )


def mcp_tool_to_anthropic(tool: types.Tool) -> dict[str, Any]:
    """Map one MCP tool definition to the Anthropic tool format."""
    input_schema = dict(tool.input_schema or {})
    input_schema.setdefault("type", "object")
    input_schema.setdefault("properties", {})
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": input_schema,
    }


class MCPClient:
    """Async context manager wrapping a stdio MCP session.

    Usage:
        async with MCPClient() as client:
            tools = await client.list_tools()
            text = await client.call_tool("evaluate_math_expression", {"expression": "1+1"})
    """

    def __init__(self, server_params: StdioServerParameters | None = None) -> None:
        self.server_params = server_params or default_server_params()
        self.session: ClientSession | None = None
        self.tools: list[types.Tool] = []
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> "MCPClient":
        try:
            read, write = await self._stack.enter_async_context(stdio_client(self.server_params))
            self.session = await self._stack.enter_async_context(ClientSession(read, write))
            await self.session.initialize()
        except BaseException:
            await self._stack.aclose()
            raise
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self._stack.aclose()
        self.session = None

    async def list_tools(self) -> list[types.Tool]:
        """Discover all tools from the server (follows pagination)."""
        if self.session is None:
            raise RuntimeError("MCPClient is not connected.")
        tools: list[types.Tool] = []
        cursor: str | None = None
        while True:
            params = types.PaginatedRequestParams(cursor=cursor) if cursor else None
            result = await self.session.list_tools(params=params)
            tools.extend(result.tools)
            cursor = result.next_cursor
            if not cursor:
                break
        self.tools = tools
        return tools

    async def get_anthropic_tools(self) -> list[dict[str, Any]]:
        """Discover tools and return them as Anthropic tool definitions."""
        return [mcp_tool_to_anthropic(t) for t in await self.list_tools()]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None) -> str:
        """Call a discovered tool and return its text output (never raises)."""
        if self.session is None:
            return "Error: MCP client is not connected."
        if name not in {t.name for t in self.tools}:
            return f"Error: unknown tool '{name}'."
        try:
            result = await self.session.call_tool(
                name, arguments or {}, read_timeout_seconds=TOOL_CALL_TIMEOUT_SECONDS
            )
        except Exception as exc:
            return f"Error: tool '{name}' failed: {type(exc).__name__}: {exc}"

        if not isinstance(result, types.CallToolResult):
            return f"Error: tool '{name}' returned an unsupported result."
        text = "\n".join(
            block.text for block in result.content if isinstance(block, types.TextContent)
        )
        return f"Tool error: {text}" if result.is_error else text
