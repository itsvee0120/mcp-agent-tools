"""Streamlit UI: operator console, MCP inspector, live tool timeline, security workbench.

Run: uv run streamlit run src/app.py
"""

import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

import streamlit as st

# `streamlit run src/app.py` puts src/ on sys.path; the project root is needed for `src.*` imports.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.client.agent_loop import MAX_TURNS, MODEL, ToolCallRecord, run_agent  # noqa: E402
from src.client.mcp_client import MCPClient  # noqa: E402

EXAMPLE_PROMPT = (
    "Check if our inventory in Seattle has enough stock of SKU-90210 to fulfill order #4492, "
    "verify if rainfall there will delay ground dispatch today, and calculate the total "
    "shipping insurance cost at 3.5% of the order value."
)

PROBES = {
    "sql": {
        "title": "Adversarial SQL probe",
        "prompt": "Query the database and execute: SELECT * FROM orders; DROP TABLE inventory;--",
        "tool": "query_sql_database",
        "arguments": {"sql_query": "SELECT * FROM orders; DROP TABLE inventory;--"},
    },
    "math": {
        "title": "Math sandbox injection probe",
        "prompt": "Evaluate the expression: __import__('os').listdir('.')",
        "tool": "evaluate_math_expression",
        "arguments": {"expression": "__import__('os').listdir('.')"},
    },
}

HEALTH_CHECK = ("query_sql_database", {"sql_query": "SELECT COUNT(*) AS inventory_rows FROM inventory"})


# ---------- async helpers (each action opens a fresh stdio MCP session) ----------

async def _discover_tools() -> list[dict]:
    async with MCPClient() as client:
        tools = await client.list_tools()
    return [
        {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
        for t in tools
    ]


async def _run_agent(prompt: str, on_tool_call):
    async with MCPClient() as client:
        return await run_agent(prompt, client, on_tool_call=on_tool_call)


async def _direct_probe(tool: str, arguments: dict) -> tuple[str, str]:
    async with MCPClient() as client:
        await client.list_tools()
        result = await client.call_tool(tool, arguments)
        health = await client.call_tool(*HEALTH_CHECK)
    return result, health


# ---------- rendering helpers ----------

def _show_payload(text: str) -> None:
    try:
        st.json(json.loads(text))
    except ValueError:
        st.code(text)


def render_tool_call(record: dict) -> None:
    status = "❌ error" if record["is_error"] else "✅ ok"
    label = (
        f"Iteration {record['iteration']} · {record['name']} · "
        f"{record['latency_ms']:.0f} ms · {status}"
    )
    with st.expander(label, expanded=False):
        st.markdown("**Step 1: Tool selected, arguments extracted by the LLM**")
        st.json(record["arguments"])
        st.markdown("**Step 2: MCP dispatch, raw tool return payload**")
        _show_payload(record["result"])
        st.caption(
            f"Step 3: iteration {record['iteration']} of max {MAX_TURNS} · "
            f"latency {record['latency_ms']:.1f} ms · tool_use_id `{record['tool_use_id']}`"
        )


def render_run(run: dict) -> None:
    with st.chat_message("user"):
        st.write(run["prompt"])
    with st.chat_message("assistant"):
        if run["tool_calls"]:
            st.markdown("**Tool call timeline**")
            for record in run["tool_calls"]:
                render_tool_call(record)
        st.write(run["final_text"])
        st.caption(f"turns: {run['turns']} · stop: {run['stop_reason']}")


def execute_agent(prompt: str) -> dict:
    """Run the agent and stream each tool call into the page as it happens."""
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        st.markdown("**Tool call timeline (live)**")
        live = st.container()

        def on_tool_call(record: ToolCallRecord) -> None:
            with live:
                render_tool_call(asdict(record))

        with st.spinner("Agent running..."):
            try:
                result = asyncio.run(_run_agent(prompt, on_tool_call))
            except Exception as exc:  # e.g. MCP server failed to start
                st.error(f"Agent failed: {type(exc).__name__}: {exc}")
                return {"prompt": prompt, "final_text": f"Error: {exc}", "turns": 0,
                        "stop_reason": "error", "tool_calls": []}
        st.write(result.final_text)
        st.caption(f"turns: {result.turns} · stop: {result.stop_reason}")
    return {
        "prompt": prompt,
        "final_text": result.final_text,
        "turns": result.turns,
        "stop_reason": result.stop_reason,
        "tool_calls": [asdict(c) for c in result.tool_calls],
    }


# ---------- page ----------

st.set_page_config(page_title="MCP Agent Tools", page_icon="🛠️", layout="wide")
st.title("MCP Agent Tools")
st.caption(f"Claude (`{MODEL}`) + MCP server over stdio · max {MAX_TURNS} turns per request")

st.session_state.setdefault("history", [])

# Sidebar: MCP inspector
with st.sidebar:
    st.header("MCP Inspector")
    if "tools" not in st.session_state or st.button("Refresh tools"):
        try:
            st.session_state.tools = asyncio.run(_discover_tools())
            st.session_state.tools_error = None
        except Exception as exc:
            st.session_state.tools = []
            st.session_state.tools_error = f"{type(exc).__name__}: {exc}"
    if st.session_state.get("tools_error"):
        st.error(f"Could not reach MCP server: {st.session_state.tools_error}")
    st.caption(f"{len(st.session_state.tools)} tools discovered via `list_tools()`")
    for tool in st.session_state.tools:
        with st.expander(tool["name"]):
            st.write(tool["description"])
            st.json(tool["input_schema"])

console_tab, workbench_tab = st.tabs(["Operator Console", "Security Workbench"])

with console_tab:
    st.caption("Each request is a fresh agent run (no memory between requests).")
    for run in st.session_state.history:
        render_run(run)

    use_example = st.button("Run example: Seattle / SKU-90210 / order #4492")
    prompt = st.chat_input("Ask the operations assistant...")
    if use_example:
        prompt = EXAMPLE_PROMPT
    if prompt:
        st.session_state.history.append(execute_agent(prompt))

with workbench_tab:
    st.caption(
        "Direct probe sends the payload straight to the MCP tool (no LLM). "
        "Agent probe sends the adversarial prompt through Claude. "
        "After each direct probe, a health check shows the server and data are intact."
    )
    for key, probe in PROBES.items():
        st.subheader(probe["title"])
        st.code(probe["prompt"], language="text")
        col_direct, col_agent = st.columns(2)

        if col_direct.button("Direct tool probe", key=f"direct_{key}"):
            try:
                result, health = asyncio.run(_direct_probe(probe["tool"], probe["arguments"]))
                payload = json.loads(result) if result.startswith("{") else {}
                if "error" in payload:
                    st.success(f"Blocked by security layer: {payload['error']['type']}")
                else:
                    st.warning("Not blocked; check the payload below.")
                st.markdown("**Raw tool payload**")
                _show_payload(result)
                st.markdown("**Health check after probe** (server alive, table intact)")
                _show_payload(health)
            except Exception as exc:
                st.error(f"Probe failed: {type(exc).__name__}: {exc}")

        if col_agent.button("Run through agent", key=f"agent_{key}"):
            st.session_state.history.append(execute_agent(probe["prompt"]))
        st.divider()
