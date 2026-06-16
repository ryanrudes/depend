from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast

from mypy.types import Instance, RawExpressionType, Type, TypeAliasType, get_proper_type

REFINED_META_ATTR = "__depend_refined__"
REFINED_META_MOD = "depend.mypy_plugin"
ANNOTATION_META_BY_SPAN: dict[tuple[int, int], RefinedMeta] = {}


@dataclass(frozen=True, slots=True)
class RefinedMeta:
    base_type: Type
    predicate_kind: str
    predicate_args: tuple[Any, ...]
    name: str
    runtime_only: bool = False


@dataclass(frozen=True, slots=True)
class FunctionContract:
    fullname: str
    parameters: tuple[RefinedMeta | None, ...]


def encode_refined_meta(meta: RefinedMeta) -> RawExpressionType:
    payload = json.dumps(
        {
            "kind": meta.predicate_kind,
            "args": list(meta.predicate_args),
            "name": meta.name,
            "runtime_only": meta.runtime_only,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return RawExpressionType(payload, "builtins.str")


def register_refined_meta(line: int, column: int, meta: RefinedMeta) -> None:
    ANNOTATION_META_BY_SPAN[(line, column)] = meta


def lookup_refined_meta(line: int, column: int) -> RefinedMeta | None:
    return ANNOTATION_META_BY_SPAN.get((line, column))


def decode_refined_meta(payload: RawExpressionType, base_type: Type) -> RefinedMeta | None:
    try:
        data = json.loads(cast(str, payload.literal_value))
    except Exception:
        return None

    kind = data.get("kind")
    name = data.get("name")
    args = data.get("args", [])
    if not isinstance(kind, str) or not isinstance(name, str) or not isinstance(args, list):
        return None
    runtime_only = bool(data.get("runtime_only", False))
    return RefinedMeta(base_type=base_type, predicate_kind=kind, predicate_args=tuple(args), name=name, runtime_only=runtime_only)


def attach_refined_meta(typ: Type, meta: RefinedMeta) -> Type:
    proper = get_proper_type(typ)
    if isinstance(proper, Instance):
        encoded = encode_refined_meta(meta)
        return cast(Type, cast(Any, proper).copy_with_extra_attr(REFINED_META_ATTR, encoded))
    return typ


def strip_refined_meta(typ: Type) -> Type:
    proper = get_proper_type(typ)
    if isinstance(proper, TypeAliasType):
        if proper.alias is None:
            return typ
        return strip_refined_meta(proper._expand_once())
    if isinstance(proper, Instance):
        return typ
    return typ


def extract_refined_meta(typ: Type) -> RefinedMeta | None:
    proper = get_proper_type(typ)
    if isinstance(proper, TypeAliasType):
        if proper.alias is None:
            return None
        return extract_refined_meta(proper._expand_once())
    if isinstance(proper, Instance) and proper.extra_attrs:
        marker = proper.extra_attrs.attrs.get(REFINED_META_ATTR)
        if isinstance(marker, RawExpressionType):
            return decode_refined_meta(marker, strip_refined_meta(proper))
    return None
