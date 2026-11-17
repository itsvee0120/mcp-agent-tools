"""Deterministic math evaluator using an AST whitelist visitor.

Never uses eval(), exec() or numexpr. Only these nodes are allowed:
Expression, BinOp, UnaryOp, numeric Constant, Call to a whitelisted math
function, and Name for whitelisted constants (pi, e).
"""

import ast
import json
import math
import operator
import time

TIMEOUT_SECONDS = 2.0
MAX_EXPRESSION_LENGTH = 300
MAX_RESULT_DIGITS = 4_000  # guards against huge powers like 9**9**9 (below Python's 4300-digit str limit)

BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
FUNCTIONS = {
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
}
CONSTANTS = {"pi": math.pi, "e": math.e}


class UnsafeExpressionError(Exception):
    """Raised when an expression contains non-whitelisted syntax."""


class _SafeEvaluator(ast.NodeVisitor):
    """Evaluates a whitelisted AST; any other node type is rejected."""

    def __init__(self, deadline: float) -> None:
        self.deadline = deadline

    def visit(self, node: ast.AST):
        if time.monotonic() > self.deadline:
            raise TimeoutError(f"Evaluation exceeded {TIMEOUT_SECONDS} seconds.")
        return super().visit(node)

    def generic_visit(self, node: ast.AST):
        raise UnsafeExpressionError(f"Disallowed syntax: {type(node).__name__}")

    def visit_Expression(self, node: ast.Expression):
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise UnsafeExpressionError("Only numeric constants are allowed.")
        return node.value

    def visit_Name(self, node: ast.Name):
        if node.id not in CONSTANTS:
            raise UnsafeExpressionError(f"Unknown name: {node.id}")
        return CONSTANTS[node.id]

    def visit_UnaryOp(self, node: ast.UnaryOp):
        op = UNARY_OPS.get(type(node.op))
        if op is None:
            raise UnsafeExpressionError(f"Disallowed operator: {type(node.op).__name__}")
        return op(self.visit(node.operand))

    def visit_BinOp(self, node: ast.BinOp):
        op = BIN_OPS.get(type(node.op))
        if op is None:
            raise UnsafeExpressionError(f"Disallowed operator: {type(node.op).__name__}")
        left, right = self.visit(node.left), self.visit(node.right)
        if isinstance(node.op, ast.Pow):
            _check_power(left, right)
        result = op(left, right)
        if isinstance(result, complex):  # e.g. (-8) ** 0.5
            raise ValueError("Complex results are not supported.")
        return result

    def visit_Call(self, node: ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
            raise UnsafeExpressionError("Only whitelisted math functions may be called.")
        if node.keywords:
            raise UnsafeExpressionError("Keyword arguments are not allowed.")
        args = [self.visit(arg) for arg in node.args]
        return FUNCTIONS[node.func.id](*args)


def _check_power(base, exponent) -> None:
    """Reject powers whose result would be unreasonably large."""
    if base in (0, 1, -1):
        return
    if abs(exponent) * math.log10(abs(base)) > MAX_RESULT_DIGITS:
        raise UnsafeExpressionError("Result too large.")


def evaluate(expression: str) -> float | int:
    """Parse and evaluate an expression safely.

    Raises:
        UnsafeExpressionError: for non-whitelisted syntax.
        TimeoutError, ArithmeticError, ValueError, SyntaxError: for invalid math.
    """
    if not isinstance(expression, str) or not expression.strip():
        raise UnsafeExpressionError("Expression must be a non-empty string.")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise UnsafeExpressionError(f"Expression exceeds {MAX_EXPRESSION_LENGTH} characters.")
    tree = ast.parse(expression.strip(), mode="eval")
    deadline = time.monotonic() + TIMEOUT_SECONDS
    return _SafeEvaluator(deadline).visit(tree)


def _error(error_type: str, message: str) -> str:
    return json.dumps({"error": {"type": error_type, "message": message}})


def calculate(expression: str) -> str:
    """Evaluate an expression and return a JSON string (never raises).

    Success: {"expression": ..., "result": ...}
    Failure: {"error": {"type": ..., "message": ...}}
    """
    try:
        result = evaluate(expression)
        if isinstance(result, float):
            result = round(result, 10)  # hide float noise like 375.90000000000003
        return json.dumps({"expression": expression, "result": result})
    except UnsafeExpressionError as exc:
        return _error("UnsafeExpressionError", str(exc))
    except SyntaxError:
        return _error("SyntaxError", "Invalid expression syntax.")
    except TimeoutError as exc:
        return _error("TimeoutError", str(exc))
    except (ArithmeticError, ValueError, TypeError) as exc:
        return _error(type(exc).__name__, str(exc))
    except Exception as exc:  # never crash the server
        return _error(type(exc).__name__, str(exc))
