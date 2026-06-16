from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from mypy.nodes import BytesExpr, Expression, FloatExpr, IntExpr, NameExpr, UnaryExpr
from mypy.plugin import CheckerPluginInterface
from mypy.types import AnyType, Instance, LiteralType, Type, TypeAliasType, get_proper_type

from .metadata import RefinedMeta, attach_refined_meta, extract_refined_meta


def literal_value(typ: Type) -> Any | None:
    proper = get_proper_type(typ)
    if isinstance(proper, LiteralType):
        return proper.value
    if isinstance(proper, Instance) and proper.last_known_value is not None:
        return proper.last_known_value.value
    return None


def marker_meta(typ: Type) -> RefinedMeta | None:
    return extract_refined_meta(typ)


def mark_type(typ: Type, meta: RefinedMeta) -> Type:
    proper = get_proper_type(typ)
    if isinstance(proper, TypeAliasType) and proper.alias is not None:
        return mark_type(proper._expand_once(), meta)
    if isinstance(proper, LiteralType):
        fallback = proper.fallback.copy_modified(last_known_value=proper)
        return attach_refined_meta(fallback, replace(meta, base_type=fallback))
    return attach_refined_meta(proper, replace(meta, base_type=proper))


def expected_text(meta: RefinedMeta) -> str:
    if meta.runtime_only:
        return "runtime-only predicate"
    kind = meta.predicate_kind
    args = meta.predicate_args
    if kind == "gt":
        return f"> {args[0]}"
    if kind == "ge":
        return f">= {args[0]}"
    if kind == "lt":
        return f"< {args[0]}"
    if kind == "le":
        return f"<= {args[0]}"
    if kind == "between":
        return f"between {args[0]} and {args[1]}"
    if kind == "non_empty":
        return "non-empty"
    if kind == "finite":
        return "finite"
    if kind == "probability":
        return "between 0 and 1"
    if kind == "strictly_increasing":
        return "strictly increasing"
    return meta.name


def is_known_predicate_compatible(actual: RefinedMeta | None, expected: RefinedMeta) -> bool:
    if expected.runtime_only:
        return True
    if actual is None:
        return True
    if actual.runtime_only:
        return True

    actual_interval = predicate_interval(actual)
    expected_interval = predicate_interval(expected)
    if actual_interval is None or expected_interval is None:
        return actual.predicate_kind == expected.predicate_kind and actual.predicate_args == expected.predicate_args
    return intervals_overlap(actual_interval, expected_interval)


def predicate_interval(meta: RefinedMeta) -> tuple[float | int, bool, float | int, bool] | None:
    kind = meta.predicate_kind
    args = meta.predicate_args
    if kind == "gt":
        return (args[0], False, math.inf, False)
    if kind == "ge":
        return (args[0], True, math.inf, False)
    if kind == "lt":
        return (-math.inf, False, args[0], False)
    if kind == "le":
        return (-math.inf, False, args[0], True)
    if kind == "between":
        return (args[0], True, args[1], True)
    if kind == "probability":
        return (0, True, 1, True)
    return None


def intervals_overlap(
    left: tuple[float | int, bool, float | int, bool],
    right: tuple[float | int, bool, float | int, bool],
) -> bool:
    low = max_lower(left, right)
    high = min_upper(left, right)
    if low is None or high is None:
        return True
    lower_value, lower_inclusive = low
    upper_value, upper_inclusive = high
    if lower_value < upper_value:
        return True
    if lower_value > upper_value:
        return False
    return lower_inclusive and upper_inclusive


def max_lower(
    left: tuple[float | int, bool, float | int, bool],
    right: tuple[float | int, bool, float | int, bool],
) -> tuple[float | int, bool] | None:
    left_value, left_inclusive, _, _ = left
    right_value, right_inclusive, _, _ = right
    if left_value > right_value:
        return left_value, left_inclusive
    if right_value > left_value:
        return right_value, right_inclusive
    return left_value, left_inclusive and right_inclusive


def min_upper(
    left: tuple[float | int, bool, float | int, bool],
    right: tuple[float | int, bool, float | int, bool],
) -> tuple[float | int, bool] | None:
    _, _, left_value, left_inclusive = left
    _, _, right_value, right_inclusive = right
    if left_value < right_value:
        return left_value, left_inclusive
    if right_value < left_value:
        return right_value, right_inclusive
    return left_value, left_inclusive and right_inclusive


def format_literal(value: Any) -> str:
    return f"Literal[{value!r}]"


def format_argument_mismatch(position: int, fullname: str, expected: RefinedMeta, actual_type: Type) -> str:
    actual_value = literal_value(actual_type)
    if actual_value is not None:
        actual_desc = format_literal(actual_value)
    else:
        actual_meta = marker_meta(actual_type)
        if actual_meta is not None:
            actual_desc = actual_meta.name
        else:
            actual_desc = str(get_proper_type(actual_type))
    return f"Argument {position} to {fullname} violates {expected.name}: expected {expected_text(expected)}, got {actual_desc}"


def maybe_error_for_arg(
    api: CheckerPluginInterface,
    fullname: str,
    position: int,
    expected: RefinedMeta,
    actual_type: Type,
    site_context: Any,
    actual_expr: Expression | None = None,
) -> None:
    actual_meta = marker_meta(actual_type)
    if is_known_predicate_compatible(actual_meta, expected):
        actual_value = literal_value(actual_type)
        if actual_value is None and actual_expr is not None:
            actual_value = expression_literal_value(actual_expr)
        if actual_value is None:
            return
        # Literal values need explicit checking even if they carry no metadata.
        if not predicate_holds(expected, actual_value):
            api.fail(format_argument_mismatch(position, fullname, expected, actual_type), site_context, code=None)
        return

    api.fail(format_argument_mismatch(position, fullname, expected, actual_type), site_context, code=None)


def predicate_holds(meta: RefinedMeta, value: Any) -> bool:
    if meta.runtime_only:
        return True
    kind = meta.predicate_kind
    args = meta.predicate_args
    if kind == "gt":
        return value > args[0]
    if kind == "ge":
        return value >= args[0]
    if kind == "lt":
        return value < args[0]
    if kind == "le":
        return value <= args[0]
    if kind == "between":
        return args[0] <= value <= args[1]
    if kind == "probability":
        return 0 <= value <= 1
    return True


def expression_literal_value(expr: Expression) -> Any | None:
    if isinstance(expr, IntExpr):
        return expr.value
    if isinstance(expr, FloatExpr):
        return expr.value
    if isinstance(expr, BytesExpr):
        return expr.value
    if isinstance(expr, NameExpr):
        if expr.name == "True":
            return True
        if expr.name == "False":
            return False
        if expr.name == "None":
            return None
        return None
    if isinstance(expr, UnaryExpr):
        inner = expression_literal_value(expr.expr)
        if inner is None:
            return None
        if expr.op == "-":
            return -inner
        if expr.op == "+":
            return +inner
    return None
