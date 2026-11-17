# mcp-agent-tools

MCP-backed tool-augmented AI assistant: FastMCP server (read-only SQL, live weather, safe AST math), stdio MCP client, OpenAI function-calling loop, Streamlit UI.

## Setup
```
uv sync
cp .env.example .env   # then add your OPENAI_API_KEY
```

## Run
- Tests: `uv run pytest -v`
- UI: `uv run streamlit run src/app.py`

_Full documentation coming in a later phase._
