from __future__ import annotations

import ast
from collections.abc import Callable
import re
from pathlib import Path
from typing import Any, cast

from mypy.plugin import AnalyzeTypeContext, CheckerPluginInterface, FunctionContext, FunctionSigContext, MethodContext, MethodSigContext, Plugin
from mypy.types import CallableType, Instance, Type, TypeAliasType, UnboundType, get_proper_type

from .analyze import analyze_annotated_type, ctx_type_placeholder, _parse_known_predicate, _root_name
from .metadata import FunctionContract, RefinedMeta, extract_refined_meta, lookup_refined_meta
from .narrow import mark_type, maybe_error_for_arg

ANNOTATED_FULLNAMES = {"typing.Annotated", "typing_extensions.Annotated"}
ENSURE_FULLNAMES = {"depend.validate.ensure", "depend.ensure"}
CHECKED_FULLNAMES = {"depend.checked.checked", "depend.checked"}


class DependPlugin(Plugin):
    def __init__(self, options: Any) -> None:
        super().__init__(options)
        self.contracts: dict[str, FunctionContract] = {}
        self._source_meta_cache: dict[tuple[str, str], RefinedMeta | None] = {}

    def get_type_analyze_hook(self, fullname: str) -> Callable[[AnalyzeTypeContext], Type] | None:
        if fullname in ANNOTATED_FULLNAMES:
            return analyze_annotated_type
        return None

    def get_function_signature_hook(self, fullname: str) -> Callable[[FunctionSigContext], CallableType] | None:
        return self._signature_hook(fullname)

    def get_method_signature_hook(self, fullname: str) -> Callable[[MethodSigContext], CallableType] | None:
        return self._signature_hook(fullname)

    def get_function_hook(self, fullname: str) -> Callable[[FunctionContext], Type] | None:
        if fullname in CHECKED_FULLNAMES:
            return self._checked_hook
        if fullname in ENSURE_FULLNAMES:
            return self._ensure_hook
        return self._call_hook(fullname)

    def get_method_hook(self, fullname: str) -> Callable[[MethodContext], Type] | None:
        return self._call_hook(fullname)

    def _signature_hook(self, fullname: str):
        def hook(ctx: FunctionSigContext | MethodSigContext) -> CallableType:
            signature = ctx.default_signature
            changed = self._store_contract_from_callable(signature, ctx.api)
            if changed:
                stripped = [strip_type(typ) for typ in signature.arg_types]
                ret_type = strip_type(signature.ret_type)
                return signature.copy_modified(arg_types=stripped, ret_type=ret_type)
            return signature

        return hook

    def _ensure_hook(self, ctx: FunctionContext) -> Type:
        if not ctx.arg_types or not ctx.arg_types[0]:
            return ctx.default_return_type

        value_type = ctx.arg_types[0][0]
        if len(ctx.arg_types) < 2 or not ctx.arg_types[1]:
            return value_type

        annotation_type = ctx.arg_types[1][0]
        meta = self._resolve_meta(annotation_type, ctx.api)
        if meta is None:
            return value_type
        return mark_type(value_type, meta)

    def _checked_hook(self, ctx: FunctionContext) -> Type:
        if ctx.arg_types and ctx.arg_types[0]:
            callable_type = get_proper_type(ctx.arg_types[0][0])
            if isinstance(callable_type, CallableType):
                self._store_contract_from_callable(callable_type, ctx.api)
                return strip_type(callable_type)
            return ctx.arg_types[0][0]
        return ctx.default_return_type

    def _store_contract_from_callable(self, callable_type: CallableType, api: CheckerPluginInterface) -> bool:
        definition = getattr(callable_type, "definition", None)
        source_arg_types: list[Type] = []
        definition_args = getattr(definition, "arguments", None)
        if isinstance(definition_args, list):
            for arg in definition_args:
                ann = getattr(arg, "type_annotation", None)
                if ann is not None:
                    source_arg_types.append(ann)

        if not source_arg_types:
            source_type = getattr(definition, "unanalyzed_type", None)
            if isinstance(source_type, CallableType):
                source_arg_types = list(source_type.arg_types)
            else:
                source_arg_types = list(callable_type.arg_types)

        params: list[RefinedMeta | None] = []
        changed = False
        for typ in source_arg_types:
            meta = self._resolve_meta(typ, api)
            params.append(meta)
            if meta is not None:
                changed = True
        if not changed:
            return False

        fullname = getattr(definition, "fullname", None)
        if not isinstance(fullname, str):
            return False
        self.contracts[fullname] = FunctionContract(fullname=fullname, parameters=tuple(params))
        return True

    def _resolve_meta(self, typ: Type, api: CheckerPluginInterface | None = None) -> RefinedMeta | None:
        meta = extract_refined_meta(typ)
        if meta is not None:
            return meta
        line = getattr(typ, "line", -1)
        column = getattr(typ, "column", -1)
        if isinstance(line, int) and isinstance(column, int):
            meta = lookup_refined_meta(line, column)
            if meta is not None:
                return meta
        alias_name = self._alias_name(typ)
        if api is not None and alias_name is not None:
            return self._resolve_meta_from_source(api, alias_name)
        return None

    def _resolve_meta_from_source(self, api: CheckerPluginInterface, alias_name: str) -> RefinedMeta | None:
        source_path = getattr(api, "path", None)
        if not isinstance(source_path, str) or not source_path:
            return None
        cache_key = (source_path, alias_name)
        if cache_key in self._source_meta_cache:
            return self._source_meta_cache[cache_key]

        meta: RefinedMeta | None = None
        try:
            text = Path(source_path).read_text(encoding="utf-8")
        except OSError:
            self._source_meta_cache[cache_key] = None
            return None

        pattern = re.compile(rf"^\s*(?:type\s+)?{re.escape(alias_name)}\s*=\s*(.+)$")
        for line in text.splitlines():
            match = pattern.match(line)
            if not match:
                continue
            rhs = match.group(1).split("#", 1)[0].strip()
            meta = _parse_refined_meta_source(rhs)
            if meta is not None:
                break

        self._source_meta_cache[cache_key] = meta
        return meta

    def _alias_name(self, typ: Type) -> str | None:
        if isinstance(typ, UnboundType):
            return typ.name
        if isinstance(typ, TypeAliasType):
            alias = typ.alias
            if alias is None:
                return None
            name = getattr(alias, "name", None)
            if isinstance(name, str):
                return name
            fullname = getattr(alias, "fullname", None)
            if isinstance(fullname, str):
                return fullname.rsplit(".", 1)[-1]
        return None

    def _call_hook(self, fullname: str):
        def hook(ctx: FunctionContext | MethodContext) -> Type:
            contract = self.contracts.get(fullname)
            if contract is None:
                return ctx.default_return_type

            for index, expected in enumerate(contract.parameters):
                if expected is None:
                    continue
                if index >= len(ctx.arg_types) or not ctx.arg_types[index]:
                    continue
                actual_type = ctx.arg_types[index][0]
                site_context = ctx.args[index][0] if index < len(ctx.args) and ctx.args[index] else ctx.context
                actual_expr = ctx.args[index][0] if index < len(ctx.args) and ctx.args[index] else None
                maybe_error_for_arg(
                    ctx.api,
                    fullname.rsplit(".", 1)[-1],
                    index + 1,
                    expected,
                    actual_type,
                    site_context,
                    actual_expr,
                )
            return ctx.default_return_type

        return hook


def strip_type(typ: Type) -> Type:
    proper = get_proper_type(typ)
    if isinstance(proper, Instance):
        if proper.extra_attrs and "__depend_refined__" in proper.extra_attrs.attrs:
            extra = proper.extra_attrs.copy()
            extra.attrs.pop("__depend_refined__", None)
            extra.immutable.discard("__depend_refined__")
            if not extra.attrs:
                return cast(Type, cast(Any, proper).copy_modified(extra_attrs=None))
            return cast(Type, cast(Any, proper).copy_modified(extra_attrs=extra))
        return proper
    if isinstance(proper, CallableType):
        return proper.copy_modified(
            arg_types=[strip_type(arg) for arg in proper.arg_types],
            ret_type=strip_type(proper.ret_type),
        )
    if isinstance(proper, TypeAliasType) and proper.alias is not None:
        return strip_type(proper._expand_once())
    return proper


def plugin(version: str) -> type[Plugin]:
    return DependPlugin


def _parse_refined_meta_source(source: str) -> RefinedMeta | None:
    try:
        expr = ast.parse(source, mode="eval").body
    except SyntaxError:
        return None

    if not isinstance(expr, ast.Subscript):
        return None
    if _root_name(expr.value) not in {"Annotated"}:
        return None

    items = _subscript_items(expr.slice)
    for item in items[1:]:
        text = ast.unparse(item)
        parsed = _parse_known_predicate(text)
        if parsed is not None:
            return parsed
        return RefinedMeta(
            base_type=ctx_type_placeholder(),
            predicate_kind="runtime",
            predicate_args=(),
            name=text,
            runtime_only=True,
        )
    return None


def _subscript_items(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, ast.Tuple):
        return list(node.elts)
    return [node]
