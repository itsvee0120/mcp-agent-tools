"""Tests 6-7: SQL injection / DDL rejection and math sandbox (no code execution)."""

import json

import pytest

from src.server.mcp_server import evaluate_math_expression, query_sql_database
from src.server.tools import sql_tool
from src.server.tools.math_tool import UnsafeExpressionError, evaluate

SQL_ATTACKS = [
    "DROP TABLE inventory",
    "UPDATE inventory SET quantity = 0",
    "INSERT INTO orders VALUES (9999, 1, 'SKU-90210', 1, 1.0, 'pending', '2026-01-01')",
    "DELETE FROM orders",
    "  delete from orders",
    "SELECT * FROM orders; DROP TABLE inventory;--",
    "SELECT 1; DELETE FROM orders",
    "SELECT * FROM orders/**/;DROP/**/TABLE inventory",
    "SELECT * FROM orders -- trailing comment",
    "SELECT * FROM orders WHERE 1=1 /* hidden */",
    "ATTACH DATABASE 'evil.db' AS evil",
    "PRAGMA table_info(orders)",
    "WITH x AS (SELECT 1) DELETE FROM orders",
    "SELECT * FROM orders WHERE order_id IN (SELECT 1) UNION SELECT * FROM orders; UPDATE orders SET status='x'",
    "",
]


def _error_type(raw: str) -> str | None:
    payload = json.loads(raw)
    return payload["error"]["type"] if "error" in payload else None


@pytest.mark.parametrize("attack", SQL_ATTACKS)
def test_sql_ddl_dml_rejection(attack):
    """Test 6: DDL/DML, stacked queries, and comments are rejected with a structured error."""
    assert _error_type(query_sql_database(attack)) == "SecurityException"
    with pytest.raises(sql_tool.SecurityException):
        sql_tool.validate_query(attack)


def test_sql_read_only_connection_blocks_writes_even_if_validation_is_bypassed(monkeypatch):
    """Test 6 (defense in depth): mode=ro + authorizer block writes without the validator."""
    monkeypatch.setattr(sql_tool, "validate_query", lambda q: q)
    for attack in ["DELETE FROM orders", "DROP TABLE inventory", "UPDATE inventory SET quantity = 0"]:
        assert _error_type(sql_tool.run_query(attack)) is not None


def test_sql_database_intact_after_attacks():
    """Test 6: after all attacks, the data is unchanged."""
    for attack in SQL_ATTACKS:
        query_sql_database(attack)
    counts = json.loads(
        query_sql_database(
            "SELECT (SELECT COUNT(*) FROM orders), (SELECT COUNT(*) FROM inventory)"
        )
    )
    assert counts["rows"] == [[12, 12]]


MATH_ATTACKS = [
    "__import__('os').listdir('.')",
    "__import__('os').system('dir')",
    "().__class__.__bases__[0].__subclasses__()",
    "open('secrets.txt').read()",
    "eval('1+1')",
    "exec('x = 1')",
    "lambda: 1",
    "[x for x in range(10)]",
    "(x := 5)",
    "sqrt.__globals__",
    "'a' * 10",
    "True + 1",
    "1 if 1 else 2",
    "abs(x=1)",
    "9 ** 9 ** 9",
    "globals()",
]


@pytest.mark.parametrize("attack", MATH_ATTACKS)
def test_math_arbitrary_code_execution_block(attack):
    """Test 7: non-whitelisted AST nodes, names, and calls are rejected; nothing executes."""
    raw = evaluate_math_expression(attack)
    payload = json.loads(raw)
    assert "result" not in payload
    assert payload["error"]["type"] == "UnsafeExpressionError"
    with pytest.raises(UnsafeExpressionError):
        evaluate(attack)


@pytest.mark.parametrize("attack", ["import os", "x = 1", "1 +"])
def test_math_rejects_statements_and_bad_syntax(attack):
    """Test 7: statements and malformed input fail at parse time with a structured error."""
    assert _error_type(evaluate_math_expression(attack)) == "SyntaxError"
