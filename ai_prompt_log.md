# AI Prompt Log

## Phase 0: Secrets setup
- **Prompt:** "please read all files in this folder, procedd with phase 0 in PLAN.md" / "please create what is missing"
- **Generated:** `.claude/settings.json` (denies Read/Edit on `.env`, `.env.local`, `.env.development`, `.env.production`, `.env.test`, `.streamlit/secrets.toml`; denies `cat`/`type`/`Get-Content` on `.env*`).
- **Bugs/issues found:** `.claude/settings.json` was missing although `PLAN.md` says it was already scaffolded. Claude could not read `.env.example` because the user-level `Read(./.env.*)` deny rule blocks it, so the user has to check its contents.
- **Fixes:** Created `.claude/settings.json`. It lists the env files by name so that `.env.example` stays readable at project level.

## Phase 1: Project setup
- **Prompt:** "next steps?" / "yes" (fix uv init output) / "next step"
- **Generated:** `pyproject.toml` edits; `src/__init__.py`, `src/server/__init__.py`, `src/client/__init__.py`, `tests/__init__.py`; empty `src/server/tools/` and `data/`; `README.md` stub. The user ran `uv init`, `uv python pin 3.11` and `uv add`.
- **Bugs/issues found:** `uv init` created a packaged layout: `requires-python = ">=3.13"` (which made the 3.11 pin fail), a `[project.scripts]` entry, a `[build-system]` section, and `src/mcp_agent_tools/`, which isn't in the assignment's layout. It also put the author's name and email in `pyproject.toml`.
- **Fixes:** Set `requires-python = ">=3.11"`. Removed `authors`, `[project.scripts]` and `[build-system]`. Deleted `src/mcp_agent_tools/`.

## Phase 2: Database
- **Prompt:** "next"
- **Generated:** `data/seed_db.py`, which uses stdlib `sqlite3` and recreates `data/enterprise_ops.db` with 4 tables (customers 8, products 8, inventory 12, orders 12; 40 rows). It includes Seattle inventory of SKU-90210 (150 units) and order #4492 (120 × SKU-90210, $10,740.00). The user ran `uv run python data/seed_db.py`.
- **Bugs/issues found:** none found.
- **Fixes:** none.

## Phase 3: SQL tool
- **Prompt:** "next"
- **Generated:** `src/server/tools/sql_tool.py`, which provides `validate_query()`, `run_query()` and `SecurityException`. Defense layers: one statement only (a single trailing `;` is allowed); no `--`, `/*` or `*/`; must start with `SELECT`; forbidden keywords matched as whole words; read-only URI (`mode=ro`); a SQLite authorizer that allows only SELECT/READ/FUNCTION; a 5 s timeout via a progress handler; a 100-row limit. It returns JSON results or a JSON `{"error": {type, message}}` and never raises.
- **Bugs/issues found:** none found (no tests yet; Tests 1 and 6 come in Phases 6 and 9).
- **Fixes:** none.

## Phase 4: Math tool
- **Prompt:** "next"
- **Generated:** `src/server/tools/math_tool.py`, which provides `evaluate()`, `calculate()` and `UnsafeExpressionError`. It parses with `ast.parse(mode="eval")` and evaluates with a whitelist `NodeVisitor`: Expression, BinOp (+ - * / // % **), UnaryOp (+ -), numeric Constant (no bool), Call to whitelisted math functions only (no keywords), and Name for `pi`/`e` only. Anything else, such as Attribute or `__import__`, is rejected by `generic_visit`. There is no `eval`, `exec` or `numexpr`. It has a 2 s deadline checked at each node, a 300-character input limit, and a power-size guard. It returns JSON results or a JSON error and never raises.
- **Bugs/issues found (self-review before handoff):** (1) The first draft allowed results up to 10,000 digits, but Python 3.11 refuses to convert integers over 4,300 digits to strings, so `json.dumps` would fail. (2) A negative base with a fractional exponent, e.g. `(-8) ** 0.5`, yields a complex number, which isn't JSON-serializable.
- **Fixes:** Lowered the digit limit to 4,000. Complex results are now rejected with a clear error.
- **Note:** The manual check command first given to the user used bash-style `\"` quoting, which broke in PowerShell. Replaced it with a PowerShell here-string piped to `uv run python -`. The user confirmed the tool output was as expected.

## Phase 5: Weather tool
- **Prompt:** "yes" (start Phase 5)
- **Generated:** `src/server/tools/weather_tool.py`, which provides `get_weather()` (async), `normalize_city()` and `WeatherError`. It calls Open-Meteo geocoding and then the forecast API via `httpx.AsyncClient` (10 s per request, 20 s overall via `asyncio.wait_for`). City input is trimmed, its whitespace collapsed and any `, region` suffix dropped, then checked against a letters-only regex. HTTP 429 is retried once after 2 s and then reported. A missing geocoding result or invalid coordinates produce a clear error. The output is sanitized into a fixed JSON shape: whitelisted numeric fields (finite floats only), a WMO weather-code description, and place names stripped of special characters. The optional `client` parameter lets tests inject a mocked transport.
- **Bugs/issues found (self-review before handoff):** The first city regex rejected names like "St. Louis", where a period is followed by a space.
- **Fixes:** The regex now allows separators of 1–2 characters between name parts.

## Phase 6: MCP server + Tests 1-3
- **Prompt:** "next"
- **Generated:** `src/server/mcp_server.py`, which registers `query_sql_database`, `get_live_weather` (async) and `evaluate_math_expression` with type hints and descriptive docstrings (the docstring becomes the tool description); it runs over stdio. Also `tests/test_server_tools.py`: Test 1 (SQL row and column values for order #4492 and Seattle stock), Test 2 (Open-Meteo mocked via `httpx.MockTransport`, checking the formatted summary) and Test 3 (`2 + 3 * (4 - 1) ** 2 == 29`, `10740 * 0.035 == 375.9`).
- **Bugs/issues found:** The installed SDK is `mcp` 2.3.0, where `FastMCP` was renamed to `MCPServer`. `mcp.server.fastmcp` now raises `ModuleNotFoundError`, so the assignment's `FastMCP` import would have failed.
- **Fixes:** The user chose to keep mcp 2.x. The server uses `from mcp.server.mcpserver import MCPServer`, which has the same `@tool()` decorator API (checked against the installed SDK source). Tools use `structured_output=False` so they return plain text JSON.

## Phase 7: MCP client + Test 4
- **Prompt:** "next"
- **Generated:** `src/client/mcp_client.py`, an `MCPClient` async context manager. It spawns the server as a child process (`sys.executable -m src.server.mcp_server`) over stdio, calls `initialize()`, and discovers tools via `session.list_tools()` with pagination. `mcp_tool_to_openai()` maps each MCP tool to `{"type": "function", "function": {name, description, parameters}}`. `call_tool()` has a 30 s read timeout, rejects tool names that weren't discovered, joins the text content, prefixes `is_error` results, and never raises. Also `tests/test_mcp_client.py` (Test 4): checks discovery of the 3 tools, their schemas (object type, string parameter, required), the OpenAI mapping shape, one real stdio tool call, and rejection of an unknown tool.
- **Bugs/issues found:** none found in the draft. Risk avoided: in mcp 2.x the Python attributes are snake_case (`Tool.input_schema`, `next_cursor`, `is_error`), whereas v1 examples use `inputSchema`. I checked the installed `mcp_types` source before writing the code.
- **Fixes:** none.
