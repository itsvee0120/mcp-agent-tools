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
