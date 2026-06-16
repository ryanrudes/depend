from __future__ import annotations

import ast
from collections.abc import Callable
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Any, cast

from mypy.copytype import copy_type
from mypy.nodes import AssignmentStmt, CallExpr, Expression, MemberExpr, NameExpr, TypeInfo, Var
from mypy.plugin import AnalyzeTypeContext, CheckerPluginInterface, ClassDefContext, FunctionContext, FunctionSigContext, MethodContext, MethodSigContext, Plugin
from mypy.types import AnyType, CallableType, Instance, LiteralType, TupleType, Type, TypeAliasType, TypeOfAny, UnboundType, get_proper_type

from .analyze import analyze_annotated_type, ctx_type_placeholder, _parse_known_predicate, _root_name
from .metadata import FunctionContract, RefinedMeta, extract_refined_meta, lookup_refined_meta
from .narrow import expression_literal_value, literal_value, mark_type, maybe_error_for_arg

ANNOTATED_FULLNAMES = {"typing.Annotated", "typing_extensions.Annotated"}
ENSURE_FULLNAMES = {"depend.validate.ensure", "depend.ensure"}
VALIDATE_FULLNAMES = {"depend.validate.validate", "depend.validate.ensure", "depend.ensure"}
CHECKED_FULLNAMES = {"depend.checked.checked", "depend.checked"}
REGISTER_FULLNAMES = {"depend.registry.register", "depend.register"}
PARENT_OF_FULLNAMES = {"depend.registry.parent_of", "depend.parent_of"}
CHILDREN_OF_FULLNAMES = {"depend.registry.children_of", "depend.children_of"}
LABEL_OF_FULLNAMES = {"depend.registry.label_of", "depend.label_of"}

RegistryKey = tuple[str, Any]


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    child_fullname: str
    child_value: Any
    child_type: Type
    child_label: str
    parent_fullname: str | None
    parent_value: Any
    parent_type: Type
    parent_label: str


def _fullname_key(fullname: str) -> RegistryKey:
    return ("fullname", fullname)


def _value_key(value: Any) -> RegistryKey:
    return ("value", value)


def _literal_str_type(text: str, api: CheckerPluginInterface | ClassDefContext | Any) -> Type:
    str_type = api.named_generic_type("builtins.str", []) if hasattr(api, "named_generic_type") else api.named_type("builtins.str", [])
    return LiteralType(text, str_type)


def _literal_type_for_value(api: Any, value: Any) -> Type | None:
    if isinstance(value, bool):
        fallback = api.named_type("builtins.bool", [])
    elif isinstance(value, int):
        fallback = api.named_type("builtins.int", [])
    elif isinstance(value, float):
        fallback = api.named_type("builtins.float", [])
    elif isinstance(value, bytes):
        fallback = api.named_type("builtins.bytes", [])
    elif isinstance(value, str):
        fallback = api.named_type("builtins.str", [])
    else:
        return None
    return LiteralType(value, fallback)


def _call_arg_by_name(call: CallExpr, name: str) -> Expression | None:
    for arg_name, arg in zip(call.arg_names, call.args, strict=False):
        if arg_name == name:
            return arg
    return None


def _semantic_expression_type(expr: Expression, api: ClassDefContext) -> Type | None:
    if isinstance(expr, NameExpr):
        node = expr.node
        if isinstance(node, Var) and node.type is not None:
            return node.type
        if isinstance(node, TypeInfo):
            return api.api.named_type(node.fullname, [])

    if isinstance(expr, MemberExpr):
        base = expr.expr
        if isinstance(base, NameExpr) and isinstance(base.node, TypeInfo):
            info = base.node
            sym = info.names.get(expr.name)
            if sym is not None and isinstance(sym.node, Var) and sym.node.type is not None:
                return sym.node.type
            if sym is not None and isinstance(sym.node, TypeInfo):
                return api.api.named_type(sym.node.fullname, [])

    typ = api.api.analyze_simple_literal_type(expr, True)
    if typ is not None:
        return typ

    value = expression_literal_value(expr)
    if value is None:
        return None
    return _literal_type_for_value(api.api, value)


def _expression_fullname(expr: Expression) -> str | None:
    if isinstance(expr, NameExpr):
        node = expr.node
        if isinstance(node, Var):
            return node.fullname
        if isinstance(node, TypeInfo):
            return node.fullname
    if isinstance(expr, MemberExpr):
        base = expr.expr
        if isinstance(base, NameExpr):
            base_node = base.node
            if isinstance(base_node, TypeInfo):
                sym = base_node.names.get(expr.name)
                if sym is not None and sym.node is not None:
                    fullname = getattr(sym.node, "fullname", None)
                    if isinstance(fullname, str):
                        return fullname
    return None


class DependPlugin(Plugin):
    def __init__(self, options: Any) -> None:
        super().__init__(options)
        self.contracts: dict[str, FunctionContract] = {}
        self._source_meta_cache: dict[tuple[str, str], RefinedMeta | None] = {}
        self._registry_entries_by_key: dict[RegistryKey, RegistryEntry] = {}
        self._registry_children_by_parent_key: dict[RegistryKey, dict[str, RegistryEntry]] = {}
        self._registry_label_by_key: dict[RegistryKey, str] = {}

    def get_type_analyze_hook(self, fullname: str) -> Callable[[AnalyzeTypeContext], Type] | None:
        if fullname in ANNOTATED_FULLNAMES:
            return analyze_annotated_type
        return None

    def get_function_signature_hook(self, fullname: str) -> Callable[[FunctionSigContext], CallableType] | None:
        return self._signature_hook(fullname)

    def get_method_signature_hook(self, fullname: str) -> Callable[[MethodSigContext], CallableType] | None:
        return self._signature_hook(fullname)

    def get_class_decorator_hook_2(self, fullname: str) -> Callable[[ClassDefContext], bool] | None:
        if fullname in REGISTER_FULLNAMES:
            return self._register_class_hook
        return None

    def get_function_hook(self, fullname: str) -> Callable[[FunctionContext], Type] | None:
        if fullname in CHECKED_FULLNAMES:
            return self._checked_hook
        if fullname in VALIDATE_FULLNAMES:
            return self._ensure_hook(fullname)
        if fullname in PARENT_OF_FULLNAMES:
            return self._parent_of_hook
        if fullname in CHILDREN_OF_FULLNAMES:
            return self._children_of_hook
        if fullname in LABEL_OF_FULLNAMES:
            return self._label_of_hook
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

    def _ensure_hook(self, fullname: str):
        def hook(ctx: FunctionContext) -> Type:
            if not ctx.arg_types or not ctx.arg_types[0]:
                return ctx.default_return_type

            value_type = ctx.arg_types[0][0]
            if len(ctx.arg_types) < 2 or not ctx.arg_types[1]:
                return value_type

            annotation_type = ctx.arg_types[1][0]
            annotation_expr = ctx.args[1][0] if len(ctx.args) > 1 and ctx.args[1] else None
            meta = self._resolve_meta(annotation_type, ctx.api, annotation_expr)
            if meta is None:
                return value_type

            actual_expr = ctx.args[0][0] if ctx.args and ctx.args[0] else None
            site_context = ctx.args[0][0] if ctx.args and ctx.args[0] else ctx.context
            maybe_error_for_arg(
                ctx.api,
                fullname.rsplit(".", 1)[-1],
                1,
                meta,
                value_type,
                site_context,
                actual_expr,
            )
            return mark_type(value_type, meta)

        return hook

    def _checked_hook(self, ctx: FunctionContext) -> Type:
        if ctx.arg_types and ctx.arg_types[0]:
            callable_type = get_proper_type(ctx.arg_types[0][0])
            if isinstance(callable_type, CallableType):
                self._store_contract_from_callable(callable_type, ctx.api)
                return strip_type(callable_type)
            return ctx.arg_types[0][0]
        return ctx.default_return_type

    def _register_class_hook(self, ctx: ClassDefContext) -> bool:
        if not isinstance(ctx.reason, CallExpr):
            return True

        to_expr = _call_arg_by_name(ctx.reason, "to")
        if to_expr is None:
            return True

        parent_semantic_type = _semantic_expression_type(to_expr, ctx)
        if parent_semantic_type is None:
            return True

        parent_type = self._registry_parent_type(to_expr, parent_semantic_type, ctx)
        parent_label = self._registry_label(parent_semantic_type, ctx.api)
        parent_keys = self._registry_keys_for_semantic_expr(to_expr, parent_semantic_type, ctx)
        if not parent_keys:
            return True

        for key in parent_keys:
            self._registry_label_by_key[key] = parent_label
            self._registry_children_by_parent_key.setdefault(key, {})

        class_fullname = ctx.cls.info.fullname
        for stmt in ctx.cls.defs.body:
            if not isinstance(stmt, AssignmentStmt) or len(stmt.lvalues) != 1:
                continue
            target = stmt.lvalues[0]
            if not isinstance(target, NameExpr):
                continue
            if target.name.startswith("_"):
                continue
            node = target.node
            if not isinstance(node, Var):
                continue

            child_type = self._literal_type_from_expr(stmt.rvalue, ctx)
            if child_type is None:
                continue

            child_type = copy_type(child_type)
            child_value = literal_value(child_type)
            if child_value is None:
                continue

            node.type = child_type

            child_fullname = node.fullname if isinstance(node.fullname, str) else f"{class_fullname}.{target.name}"
            child_label = f"{parent_label}:{child_value}"
            entry = RegistryEntry(
                child_fullname=child_fullname,
                child_value=child_value,
                child_type=child_type,
                child_label=child_label,
                parent_fullname=ctx.cls.info.fullname,
                parent_value=literal_value(parent_type),
                parent_type=parent_type,
                parent_label=parent_label,
            )
            self._store_registry_entry(entry, parent_keys)
        return True

    def _parent_of_hook(self, ctx: FunctionContext) -> Type:
        if not ctx.args or not ctx.args[0]:
            return ctx.default_return_type
        entry = self._lookup_registry_entry(ctx.args[0][0], ctx)
        if entry is None:
            return ctx.default_return_type
        return entry.parent_type

    def _children_of_hook(self, ctx: FunctionContext) -> Type:
        if not ctx.args or not ctx.args[0]:
            return ctx.default_return_type
        entries = self._lookup_registry_children(ctx.args[0][0], ctx)
        if not entries:
            return ctx.default_return_type

        ordered = sorted(entries.values(), key=lambda entry: (repr(entry.child_value), entry.child_fullname))
        items = [entry.child_type for entry in ordered]
        fallback_item = AnyType(TypeOfAny.special_form)
        fallback = ctx.api.named_generic_type("builtins.tuple", [fallback_item])
        return TupleType(items, fallback)

    def _label_of_hook(self, ctx: FunctionContext) -> Type:
        if not ctx.args or not ctx.args[0]:
            return ctx.default_return_type
        label = self._lookup_registry_label(ctx.args[0][0], ctx)
        if label is None:
            return ctx.default_return_type
        return _literal_str_type(label, ctx.api)

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

    def _resolve_meta(
        self,
        typ: Type,
        api: CheckerPluginInterface | None = None,
        expr: Expression | None = None,
    ) -> RefinedMeta | None:
        meta = extract_refined_meta(typ)
        if meta is not None:
            return meta
        proper = get_proper_type(typ)
        if isinstance(proper, TypeAliasType) and proper.alias is not None:
            meta = extract_refined_meta(proper._expand_once())
            if meta is not None:
                return meta
        line = getattr(typ, "line", -1)
        column = getattr(typ, "column", -1)
        if isinstance(line, int) and isinstance(column, int):
            meta = lookup_refined_meta(line, column)
            if meta is not None:
                return meta
        alias_name = self._alias_name(typ)
        if alias_name is None and expr is not None:
            alias_name = self._alias_name_from_expr(expr)
        if api is not None and alias_name is not None:
            return self._resolve_meta_from_source(api, alias_name)
        return None

    def _store_registry_entry(self, entry: RegistryEntry, parent_keys: list[RegistryKey]) -> None:
        child_keys = [_fullname_key(entry.child_fullname)]
        if entry.child_value is not None:
            child_keys.append(_value_key(entry.child_value))

        for key in child_keys:
            self._registry_entries_by_key[key] = entry
            self._registry_label_by_key[key] = entry.child_label

        for key in parent_keys:
            self._registry_children_by_parent_key.setdefault(key, {})[entry.child_fullname] = entry

    def _lookup_registry_entry(self, expr: Expression, ctx: FunctionContext) -> RegistryEntry | None:
        for key in self._registry_keys_for_expression(expr, ctx):
            entry = self._registry_entries_by_key.get(key)
            if entry is not None:
                return entry
        return None

    def _lookup_registry_children(self, expr: Expression, ctx: FunctionContext) -> dict[str, RegistryEntry] | None:
        for key in self._registry_keys_for_expression(expr, ctx):
            children = self._registry_children_by_parent_key.get(key)
            if children is not None:
                return children
        return None

    def _lookup_registry_label(self, expr: Expression, ctx: FunctionContext) -> str | None:
        for key in self._registry_keys_for_expression(expr, ctx):
            label = self._registry_label_by_key.get(key)
            if label is not None:
                return label
        return None

    def _registry_keys_for_expression(self, expr: Expression, ctx: FunctionContext) -> list[RegistryKey]:
        keys: list[RegistryKey] = []
        fullname = _expression_fullname(expr)
        if fullname is not None:
            keys.append(_fullname_key(fullname))
        typ = ctx.api.get_expression_type(expr)
        if typ is not None:
            value = literal_value(typ)
            if value is not None:
                keys.append(_value_key(value))
        return keys

    def _registry_keys_for_semantic_expr(self, expr: Expression, typ: Type, ctx: ClassDefContext) -> list[RegistryKey]:
        keys: list[RegistryKey] = []
        fullname = _expression_fullname(expr)
        if fullname is not None:
            keys.append(_fullname_key(fullname))
        value = literal_value(typ)
        if value is None:
            value = literal_value(ctx.api.analyze_simple_literal_type(expr, True) or typ)
        if value is not None:
            keys.append(_value_key(value))
        return keys

    def _registry_parent_type(self, expr: Expression, typ: Type, ctx: ClassDefContext) -> Type:
        if isinstance(expr, MemberExpr):
            base = expr.expr
            if isinstance(base, NameExpr) and isinstance(base.node, TypeInfo) and base.node.is_enum:
                enum_type = ctx.api.named_type(base.node.fullname, [])
                return LiteralType(expr.name, enum_type)
        return copy_type(typ)

    def _literal_type_from_expr(self, expr: Expression, ctx: ClassDefContext) -> Type | None:
        typ = ctx.api.analyze_simple_literal_type(expr, True)
        if typ is not None:
            return typ
        value = expression_literal_value(expr)
        if value is None:
            return None
        return _literal_type_for_value(ctx.api, value)

    def _registry_label(self, typ: Type, api: Any) -> str:
        value = literal_value(typ)
        if value is not None:
            return str(value)
        return str(get_proper_type(typ))

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
            return typ.name.rsplit(".", 1)[-1]
        if isinstance(typ, TypeAliasType):
            alias = typ.alias
            if alias is None:
                return None
            name = getattr(alias, "name", None)
            if isinstance(name, str):
                return name.rsplit(".", 1)[-1]
            fullname = getattr(alias, "fullname", None)
            if isinstance(fullname, str):
                return fullname.rsplit(".", 1)[-1]
        return None

    def _alias_name_from_expr(self, expr: Expression) -> str | None:
        if isinstance(expr, NameExpr):
            node = expr.node
            name = getattr(node, "name", None)
            if isinstance(name, str):
                return name.rsplit(".", 1)[-1]
            fullname = getattr(node, "fullname", None)
            if isinstance(fullname, str):
                return fullname.rsplit(".", 1)[-1]
        if isinstance(expr, MemberExpr):
            return expr.name.rsplit(".", 1)[-1]
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
