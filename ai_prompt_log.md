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
