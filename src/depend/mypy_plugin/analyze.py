from __future__ import annotations

import ast
from typing import Any

from mypy.plugin import AnalyzeTypeContext
from mypy.types import AnyType, RawExpressionType, Type, TypeOfAny

from .metadata import RefinedMeta, attach_refined_meta, register_refined_meta

KNOWN_PREDICATES = {
    "GreaterThan": "gt",
    "GreaterEqual": "ge",
    "LessThan": "lt",
    "LessEqual": "le",
    "Between": "between",
    "NonEmpty": "non_empty",
    "Finite": "finite",
    "Probability": "probability",
    "StrictlyIncreasing": "strictly_increasing",
}


def analyze_annotated_type(ctx: AnalyzeTypeContext) -> Type:
    raw = ctx.type
    if not raw.args:
        return ctx.api.named_type("builtins.object", [])

    base = ctx.api.analyze_type(raw.args[0])
    meta = _parse_metadata(raw.args[1:])
    if meta is None:
        return base
    register_refined_meta(ctx.context.line, ctx.context.column, meta)
    return attach_refined_meta(base, meta)


def _parse_metadata(items: tuple[Any, ...]) -> RefinedMeta | None:
    for item in items:
        text = _metadata_text(item)
        if text is None:
            continue
        parsed = _parse_known_predicate(text)
        if parsed is not None:
            return parsed
        return RefinedMeta(base_type=ctx_type_placeholder(), predicate_kind="runtime", predicate_args=(), name=text, runtime_only=True)
    return None


def _metadata_text(item: Any) -> str | None:
    if isinstance(item, RawExpressionType):
        return str(item.literal_value)
    if hasattr(item, "literal_value"):
        literal_value = getattr(item, "literal_value")
        if literal_value is not None:
            return str(literal_value)
    text = str(item)
    return text if text else None


def _parse_known_predicate(text: str) -> RefinedMeta | None:
    try:
        expr = ast.parse(text, mode="eval").body
    except SyntaxError:
        return None

    if isinstance(expr, ast.Name):
        predicate_name = expr.id.rsplit(".", 1)[-1]
        kind = KNOWN_PREDICATES.get(predicate_name)
        if kind is None or kind == "between":
            return None
        if kind in {"non_empty", "finite", "probability", "strictly_increasing"}:
            return RefinedMeta(base_type=ctx_type_placeholder(), predicate_kind=kind, predicate_args=(), name=predicate_name, runtime_only=False)
        return None

    if isinstance(expr, ast.Subscript):
        predicate_name = _root_name(expr.value)
        kind = KNOWN_PREDICATES.get(predicate_name)
        if kind is None:
            return None
        args = _extract_args(expr.slice)
        if kind in {"gt", "ge", "lt", "le"} and len(args) == 1:
            return RefinedMeta(base_type=ctx_type_placeholder(), predicate_kind=kind, predicate_args=(args[0],), name=f"{predicate_name}[{args[0]!r}]", runtime_only=False)
        if kind == "between" and len(args) == 2:
            return RefinedMeta(base_type=ctx_type_placeholder(), predicate_kind=kind, predicate_args=(args[0], args[1]), name=f"{predicate_name}[{args[0]!r}, {args[1]!r}]", runtime_only=False)
    return None


def _root_name(expr: ast.AST) -> str:
    if isinstance(expr, ast.Name):
        return expr.id.rsplit(".", 1)[-1]
    if isinstance(expr, ast.Attribute):
        return expr.attr
    if isinstance(expr, ast.Subscript):
        return _root_name(expr.value)
    return ""


def _extract_args(node: ast.AST) -> tuple[Any, ...]:
    if isinstance(node, ast.Tuple):
        return tuple(ast.literal_eval(item) for item in node.elts)
    return (ast.literal_eval(node),)


def ctx_type_placeholder() -> Type:
    # The base type is filled in later from the analyzed expression.
    return AnyType(TypeOfAny.explicit)
