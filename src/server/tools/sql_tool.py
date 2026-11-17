"""Read-only SQL query runner for data/enterprise_ops.db.

Defense layers:
1. Query validation: single statement, must start with SELECT, no comments,
   no forbidden keywords (DDL/DML/ATTACH/PRAGMA...).
2. SQLite opened with URI ``mode=ro`` (read-only connection).
3. SQLite authorizer that only permits SELECT/READ/FUNCTION actions.
4. Execution timeout via progress handler, and a row limit.
"""

import json
import re
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "enterprise_ops.db"
TIMEOUT_SECONDS = 5.0
MAX_ROWS = 100
MAX_QUERY_LENGTH = 2000

FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE",
    "TRUNCATE", "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REINDEX", "ANALYZE",
)
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE)
_SELECT_RE = re.compile(r"^SELECT\b", re.IGNORECASE)

_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}


class SecurityException(Exception):
    """Raised when a query violates the read-only security policy."""


def validate_query(sql_query: str) -> str:
    """Validate a query against the read-only policy and return the cleaned query.

    Raises:
        SecurityException: if the query is not a single, comment-free SELECT.
    """
    if not isinstance(sql_query, str) or not sql_query.strip():
        raise SecurityException("Query must be a non-empty string.")
    if len(sql_query) > MAX_QUERY_LENGTH:
        raise SecurityException(f"Query exceeds {MAX_QUERY_LENGTH} characters.")

    query = sql_query.strip()
    if query.endswith(";"):
        query = query[:-1].rstrip()  # allow one trailing semicolon only

    if ";" in query:
        raise SecurityException("Multiple statements are not allowed.")
    if "--" in query or "/*" in query or "*/" in query:
        raise SecurityException("SQL comments are not allowed.")
    if not _SELECT_RE.match(query):
        raise SecurityException("Only SELECT statements are allowed.")
    match = _FORBIDDEN_RE.search(query)
    if match:
        raise SecurityException(f"Forbidden keyword: {match.group(1).upper()}.")
    return query


def _authorizer(action: int, *_args) -> int:
    """Deny every SQLite action except reading data."""
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def _error(error_type: str, message: str) -> str:
    return json.dumps({"error": {"type": error_type, "message": message}})


def run_query(sql_query: str, db_path: Path = DB_PATH) -> str:
    """Run a read-only SELECT and return a JSON string.

    Success: {"columns": [...], "rows": [[...]], "row_count": n, "truncated": bool}
    Failure: {"error": {"type": ..., "message": ...}} (never raises).
    """
    try:
        query = validate_query(sql_query)
    except SecurityException as exc:
        return _error("SecurityException", str(exc))

    if not db_path.exists():
        return _error("DatabaseError", "Database file not found.")

    conn = None
    try:
        conn = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
        conn.set_authorizer(_authorizer)
        deadline = time.monotonic() + TIMEOUT_SECONDS
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 1000)

        cursor = conn.execute(query)
        columns = [col[0] for col in cursor.description or []]
        rows = cursor.fetchmany(MAX_ROWS + 1)
        truncated = len(rows) > MAX_ROWS
        rows = [list(r) for r in rows[:MAX_ROWS]]
        return json.dumps(
            {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": truncated}
        )
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc):
            return _error("TimeoutError", f"Query exceeded {TIMEOUT_SECONDS} seconds.")
        return _error("OperationalError", str(exc))
    except sqlite3.DatabaseError as exc:
        return _error("DatabaseError", str(exc))
    except Exception as exc:  # never crash the server
        return _error(type(exc).__name__, str(exc))
    finally:
        if conn is not None:
            conn.close()
