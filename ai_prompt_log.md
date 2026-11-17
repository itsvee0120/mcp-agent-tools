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

## Phase 8: Agent loop + Test 5
- **Prompt:** "next", then "use antrhopic instead" (switch the LLM provider from OpenAI to Anthropic)
- **Generated:** `src/client/agent_loop.py`, which provides `run_agent()`: a manual loop over `AsyncAnthropic().beta.messages.create` (model `claude-opus-5-5`, effort `medium`, server-side refusal fallback `fallbacks="default"`) with a hard `max_turns=5`. Tools come from the MCP server at runtime. The full assistant `content` is appended unchanged. Each `tool_use` is dispatched via MCP, and all `tool_result` blocks for a turn (matching `tool_use_id`, `is_error` on failures) go back in one user message. Refusals and API errors (auth, 429, HTTP status, connection) are returned as text, never raised. Each call is recorded with its iteration, arguments, raw result and latency for the UI. The system prompt marks tool output as untrusted data. Also Test 5 in `tests/test_mcp_client.py`: a scripted fake LLM with the real MCP server runs SQL then Math and must end with an assistant message within 3 turns; it also checks `tool_use_id` matching and that tools were discovered.
- **Changes from switching to Anthropic:** `mcp_client.py` now maps MCP tools to the Anthropic format `{name, description, input_schema}` (`mcp_tool_to_anthropic`, `get_anthropic_tools`) instead of OpenAI's `{"type": "function", ...}`. Test 4 and README were updated. Anthropic has no `role="tool"`: tool output goes back as a `tool_result` block in a `user` message.
- **Tests:** The user ran `uv run pytest tests/test_mcp_client.py -v`; Tests 4 and 5 passed.
- **Bugs/issues found:** none found.
- **Fixes:** none.

## Phase 9: Security tests
- **Prompt:** "next"
- **Generated:** `tests/test_security.py`.
  - **Test 6** runs 15 SQL attacks (DROP, UPDATE, INSERT, DELETE, lowercase, stacked `;`, `/**/` and `--` comments, ATTACH, PRAGMA, a CTE followed by DELETE, empty input) through the MCP tool function. Each must return a `SecurityException` error, and `validate_query` must raise. A defense-in-depth test disables the validator to show that the read-only connection and authorizer still block writes, and a check confirms row counts are unchanged after all attacks.
  - **Test 7** runs 16 math payloads (`__import__`, dunder or attribute chains, `open`/`eval`/`exec`/`globals`, lambda, comprehension, walrus, string and bool constants, ternary, keyword arguments, a huge power). Each must return `UnsafeExpressionError` with no result. Statements and malformed input must return `SyntaxError`.
- **Tests:** The user ran `uv run pytest -v`; all 41 tests passed (3 tool tests, 2 client tests, 36 security tests).
- **Bugs/issues found:** none found.
- **Fixes:** none.

## Phase 10: AI audit

### Initial prompt
The code was generated with Claude Code (Claude Opus 5.5), working phase by phase. The anchor prompt was `PLAN.md` (stack, security rules, phases), together with the assignment text in `ASSIGNMENT.md`. Each phase was started with a short prompt ("next", "yes", "use antrhopic instead"); these are logged per phase above. The assignment's sample prompt was not pasted verbatim. Its requirements (read-only SQLite URI, AST math without eval/exec, `list_tools()` discovery, multi-turn loop with `max_turns=5`) were part of `PLAN.md` from the start.

### Flaws found in the AI-generated code (all real, from this project)
1. **API hallucination risk: FastMCP import (Phase 6).** The plan and assignment both say `from mcp.server.fastmcp import FastMCP`. In the installed `mcp` 2.3.0 that module only raises `ModuleNotFoundError` (FastMCP was renamed `MCPServer`). Code written from memory would have crashed the server at import time.
   - **Refactor:** Checked the installed SDK source and used `from mcp.server.mcpserver import MCPServer`, confirming that its `@tool()` decorator returns the original function. The user chose to stay on 2.x.
2. **Math evaluator crashed on valid input (Phase 4).** (a) The first size cap allowed results of up to 10,000 digits, but Python 3.11 refuses to convert integers over 4,300 digits to strings, so `json.dumps` would fail. (b) `(-8) ** 0.5` yields a `complex`, which isn't JSON-serializable.
   - **Refactor:** Cap of 4,000 digits, enforced before computing a power (`_check_power`, using a log10 estimate). Complex results are rejected with a clear `ValueError`.
3. **Input validation too strict (Phase 5).** The first city regex rejected real names like "St. Louis".
   - **Refactor:** Separators of 1–2 characters are now allowed between name parts.
4. **Project scaffolding (Phase 1).** `uv init` produced `requires-python >= 3.13` (which made the 3.11 pin fail), an unused packaged layout (`src/mcp_agent_tools`, `[project.scripts]`, `[build-system]`), and the author's name and email in `pyproject.toml`, which would have been published.
   - **Refactor:** Set `>=3.11`, removed the package leftovers and removed the `authors` block.
5. **Wrong shell syntax (Phase 4).** A verification command used bash `\"` quoting, which PowerShell misparsed and tried to execute itself.
   - **Refactor:** Switched to a PowerShell here-string piped to `uv run python -`.

### Required audit checklist (final code, verified by tests)
| Risk | What the code does | Evidence |
|---|---|---|
| SQL injection / read-only bypass | Not substring-only. One statement only (any `;` except a single trailing one is rejected), no `--`/`/* */`, must start with `SELECT`, whole-word keyword blocklist, **plus** a `mode=ro` URI connection, **plus** a SQLite authorizer allowing only SELECT/READ/FUNCTION, 5 s timeout, 100-row cap. | Test 6: 15 attacks rejected; with the validator disabled, writes are still blocked; row counts unchanged. |
| Math ACE (`eval`, `__import__`) | `ast.parse(mode="eval")` + whitelist `NodeVisitor`; `generic_visit` rejects every other node. No `eval`, `exec` or `numexpr` anywhere. Calls allowed only on a bare whitelisted function name with no keywords. | Test 7: 16 payloads rejected, including `__import__('os').listdir('.')` and subclass escapes. |
| Schema translation mismatch | MCP `input_schema` maps to Anthropic `{name, description, input_schema}`; tools come from `list_tools()` (with pagination), never hardcoded. The 2.x snake_case attribute names were checked against the SDK source. | Test 4 checks shape and schemas; Test 5 checks that the discovered tools reach the LLM request. |
| Infinite loops / state growth | Hard `max_turns=5`; tool errors become `tool_result` with `is_error` (never raised); API errors, refusals and the turn limit return an `AgentResult` instead of crashing. Per-tool timeouts (SQL 5 s, math 2 s, weather 10/20 s, MCP call 30 s). | Test 5: SQL then Math finishes in 3 turns with an `assistant` message last. |

## Phase 11: Streamlit UI
- **Prompt:** "next phas"
- **Generated:** `src/app.py` with:
  - **Sidebar MCP Inspector:** tools from `list_tools()` with their descriptions and JSON schemas, plus a refresh button.
  - **Operator Console tab:** chat input, a one-click example prompt (the Seattle / SKU-90210 / #4492 scenario), and run history.
  - **Live tool-call timeline:** one expander per call showing Step 1 (arguments chosen by the LLM), Step 2 (the raw MCP payload) and Step 3 (iteration, latency, `tool_use_id`).
  - **Security Workbench tab:** the two required probes. Each can be run as a direct MCP tool call (no LLM; shows the "Blocked by security layer" badge, the raw payload, and a health check showing the server is alive and the inventory table intact) or through the agent.

  `agent_loop.run_agent()` gained an optional `on_tool_call` callback so the UI shows each call as it happens. Each UI action opens a fresh stdio MCP session (simple; no shared event loop across Streamlit reruns). `app.py` adds the project root to `sys.path` because `streamlit run src/app.py` only adds `src/`.
- **Bugs/issues found:** none found (UI not yet run).
- **Fixes:** none.
