from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any


class Expr:
    def __str__(self) -> str:
        return format_expr(self)


@dataclass(frozen=True, slots=True)
class SymbolExpr(Expr):
    name: str


@dataclass(frozen=True, slots=True)
class ConstExpr(Expr):
    value: int


@dataclass(frozen=True, slots=True)
class BinaryExpr(Expr):
    op: str
    left: Expr
    right: Expr


def parse_expr(value: str | int | Expr) -> Expr:
    if isinstance(value, Expr):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return ConstExpr(value)
    if isinstance(value, str):
        parsed = ast.parse(value, mode="eval")
        return _parse_ast(parsed.body)
    raise TypeError(f"unsupported expression value: {value!r}")


def eval_expr(expr: Expr, symbols: dict[str, int] | Any) -> int:
    if isinstance(expr, SymbolExpr):
        return symbols[expr.name]
    if isinstance(expr, ConstExpr):
        return expr.value
    if isinstance(expr, BinaryExpr):
        left = eval_expr(expr.left, symbols)
        right = eval_expr(expr.right, symbols)
        if expr.op == "+":
            return left + right
        if expr.op == "-":
            return left - right
        if expr.op == "*":
            return left * right
        raise ValueError(f"unsupported operator: {expr.op!r}")
    raise TypeError(f"unsupported expression: {expr!r}")


def format_expr(expr: Expr) -> str:
    if isinstance(expr, SymbolExpr):
        return expr.name
    if isinstance(expr, ConstExpr):
        return str(expr.value)
    if isinstance(expr, BinaryExpr):
        return f"{_wrap(expr.left, expr.op)} {expr.op} {_wrap(expr.right, expr.op, right=True)}"
    raise TypeError(f"unsupported expression: {expr!r}")


def _wrap(expr: Expr, op: str, *, right: bool = False) -> str:
    if not isinstance(expr, BinaryExpr):
        return format_expr(expr)

    precedence = {"+": 1, "-": 1, "*": 2}
    expr_prec = precedence[expr.op]
    op_prec = precedence[op]

    needs_parens = expr_prec < op_prec
    if right and op in {"-", "/"}:
        needs_parens = needs_parens or expr_prec == op_prec
    if needs_parens:
        return f"({format_expr(expr)})"
    return format_expr(expr)


def _parse_ast(node: ast.AST) -> Expr:
    if isinstance(node, ast.Name):
        return SymbolExpr(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return ConstExpr(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
        op = "+" if isinstance(node.op, ast.Add) else "-" if isinstance(node.op, ast.Sub) else "*"
        return BinaryExpr(op=op, left=_parse_ast(node.left), right=_parse_ast(node.right))
    raise ValueError(f"unsupported expression syntax: {ast.dump(node, include_attributes=False)}")
