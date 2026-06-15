from __future__ import annotations

import types
from typing import Any, Annotated, Literal, Union, get_args, get_origin

from .context import Context
from .errors import ValidationError, summarize_value
from .expressions import Expr, SymbolExpr
from .proofs import RequiresProofAnnotation, validate_requires_proof
from .predicates import Predicate
from .numpy.dtype import DTypeAnnotation
from .numpy.ndarray import NDArrayAnnotation, describe_ndarray, load_numpy
from .numpy.shape import AnyDim, ShapeAnnotation
from .sized import SizedAnnotation


def validate(value: Any, annotation: Any, ctx: Context | None = None) -> Any:
    context = ctx or Context()
    _validate(value, annotation, context)
    return value


def ensure(value: Any, annotation: Any) -> Any:
    validate(value, annotation)
    return value


def is_valid(value: Any, annotation: Any) -> bool:
    try:
        validate(value, annotation)
        return True
    except ValidationError:
        return False


def _validate(value: Any, annotation: Any, ctx: Context) -> None:
    if annotation is Any:
        return
    if annotation is None or annotation is type(None):
        if value is not None:
            raise ValidationError(path=ctx.path, expected="None", actual=summarize_value(value), context=dict(ctx.symbols))
        return

    if isinstance(annotation, Predicate):
        annotation.validate(value, ctx)
        return

    if isinstance(annotation, SizedAnnotation):
        _validate_sized(value, annotation, ctx)
        return

    if isinstance(annotation, RequiresProofAnnotation):
        validate_requires_proof(value, annotation, ctx)
        return

    if isinstance(annotation, NDArrayAnnotation):
        _validate_ndarray(value, annotation, ctx)
        return

    origin = get_origin(annotation)

    if origin is Annotated:
        base, *metadata = get_args(annotation)
        _validate(value, base, ctx)
        for meta in metadata:
            _validate_metadata(value, meta, ctx)
        return

    if _is_union(annotation):
        _validate_union(value, annotation, ctx)
        return

    if origin is Literal:
        _validate_literal(value, annotation, ctx)
        return

    if origin in (list, set, frozenset):
        _validate_collection(value, annotation, origin, get_args(annotation), ctx)
        return

    if origin is tuple:
        _validate_tuple(value, annotation, get_args(annotation), ctx)
        return

    if origin is dict:
        _validate_dict(value, annotation, get_args(annotation), ctx)
        return

    if isinstance(annotation, type):
        if not isinstance(value, annotation):
            raise ValidationError(
                path=ctx.path,
                expected=annotation.__name__,
                actual=summarize_value(value),
                context=dict(ctx.symbols),
            )
        return

    raise ValidationError(
        path=ctx.path,
        expected=_annotation_label(annotation),
        actual=summarize_value(value),
        details="unsupported annotation form",
        context=dict(ctx.symbols),
    )


def _validate_metadata(value: Any, metadata: Any, ctx: Context) -> None:
    if isinstance(metadata, Predicate):
        metadata.validate(value, ctx)
        return
    if isinstance(metadata, SizedAnnotation):
        _validate_sized(value, metadata, ctx)
        return
    if hasattr(metadata, "validate"):
        metadata.validate(value, ctx)


def _validate_collection(value: Any, annotation: Any, origin: type[Any], args: tuple[Any, ...], ctx: Context) -> None:
    if not isinstance(value, origin):
        raise ValidationError(
            path=ctx.path,
            expected=_annotation_label(annotation),
            actual=summarize_value(value),
            context=dict(ctx.symbols),
        )

    if not args:
        return

    item_annotation = args[0]
    for index, item in enumerate(value):
        _validate(item, item_annotation, ctx.child(f"[{index}]"))


def _validate_tuple(value: Any, annotation: Any, args: tuple[Any, ...], ctx: Context) -> None:
    if not isinstance(value, tuple):
        raise ValidationError(path=ctx.path, expected=_annotation_label(annotation), actual=summarize_value(value), context=dict(ctx.symbols))

    if len(args) == 2 and args[1] is Ellipsis:
        item_annotation = args[0]
        for index, item in enumerate(value):
            _validate(item, item_annotation, ctx.child(f"[{index}]"))
        return

    if len(value) != len(args):
        raise ValidationError(
            path=ctx.path,
            expected=_annotation_label(annotation),
            actual=summarize_value(value),
            context=dict(ctx.symbols),
        )

    for index, (item, item_annotation) in enumerate(zip(value, args, strict=True)):
        _validate(item, item_annotation, ctx.child(f"[{index}]"))


def _validate_dict(value: Any, annotation: Any, args: tuple[Any, ...], ctx: Context) -> None:
    if not isinstance(value, dict):
        raise ValidationError(path=ctx.path, expected=_annotation_label(annotation), actual=summarize_value(value), context=dict(ctx.symbols))

    if not args:
        return

    key_annotation = args[0]
    value_annotation = args[1] if len(args) > 1 else Any
    for key, item in value.items():
        _validate(key, key_annotation, ctx.child(f"[key {summarize_value(key)}]"))
        _validate(item, value_annotation, ctx.child(f"[{summarize_value(key)}]"))


def _validate_union(value: Any, annotation: Any, ctx: Context) -> None:
    options = get_args(annotation)
    failures: list[ValidationError] = []
    for option in options:
        branch_ctx = ctx.fork()
        try:
            _validate(value, option, branch_ctx)
            return
        except ValidationError as exc:
            failures.append(exc)

    expected = " | ".join(_annotation_label(option) for option in options)
    details = "did not match any union option"
    if failures:
        details = f"{details}; first failure: {failures[0].expected}"
    raise ValidationError(path=ctx.path, expected=expected, actual=summarize_value(value), details=details, context=dict(ctx.symbols))


def _validate_literal(value: Any, annotation: Any, ctx: Context) -> None:
    options = get_args(annotation)
    if value not in options:
        raise ValidationError(
            path=ctx.path,
            expected=_annotation_label(annotation),
            actual=summarize_value(value),
            context=dict(ctx.symbols),
        )


def _validate_sized(value: Any, annotation: SizedAnnotation, ctx: Context) -> None:
    _validate(value, annotation.container_annotation, ctx)

    try:
        actual_length = len(value)
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(
            path=ctx.path,
            expected=f"len({ctx.path[-1] if ctx.path else 'value'}) == {annotation.length_expr}",
            actual=summarize_value(value),
            details=f"value does not support len(): {exc.__class__.__name__}: {exc}",
            context=dict(ctx.symbols),
        ) from exc

    expr = annotation.length_expr
    if isinstance(expr, SymbolExpr):
        ctx.bind_symbol(expr.name, actual_length, source=ctx.path[-1] if ctx.path else "value")
        return

    expected_length = ctx.resolve_expr(expr)
    if expected_length != actual_length:
        raise ValidationError(
            path=ctx.path,
            expected=f"len({ctx.path[-1] if ctx.path else 'value'}) == {expr}",
            actual=f"len(...) = {actual_length}",
            details=_symbol_details(ctx),
            context=dict(ctx.symbols),
        )


def _validate_ndarray(value: Any, annotation: NDArrayAnnotation, ctx: Context) -> None:
    np = load_numpy()
    if np is None:
        raise ValidationError(
            path=ctx.path,
            expected=_annotation_label(annotation),
            actual=summarize_value(value),
            details="NumPy is not installed",
            context=dict(ctx.symbols),
        )

    if not isinstance(value, np.ndarray):
        raise ValidationError(
            path=ctx.path,
            expected=_annotation_label(annotation),
            actual=summarize_value(value),
            context=dict(ctx.symbols),
        )

    _validate_ndarray_shape(value, annotation.shape, ctx)
    if annotation.dtype is not None:
        _validate_ndarray_dtype(value, annotation.dtype, ctx)


def _validate_ndarray_shape(value: Any, shape: ShapeAnnotation, ctx: Context) -> None:
    actual_shape = getattr(value, "shape", ())
    if len(actual_shape) != len(shape.dims):
        raise ValidationError(
            path=ctx.path,
            expected=_annotation_label(shape),
            actual=describe_ndarray(value),
            details=f"rank {len(actual_shape)} does not match expected rank {len(shape.dims)}",
            context=dict(ctx.symbols),
        )

    for index, (actual_dim, dim) in enumerate(zip(actual_shape, shape.dims, strict=True)):
        actual_int = int(actual_dim)
        source = ctx.path[-1] if ctx.path else f"shape[{index}]"
        if dim is AnyDim:
            continue
        if isinstance(dim, SymbolExpr):
            ctx.bind_symbol(dim.name, actual_int, source=source)
            continue
        if not isinstance(dim, Expr):
            raise ValidationError(
                path=ctx.path,
                expected=_annotation_label(shape),
                actual=describe_ndarray(value),
                details=f"unsupported shape dimension {dim!r}",
                context=dict(ctx.symbols),
            )
        expected_dim = ctx.resolve_expr(dim)
        if expected_dim != actual_int:
            raise ValidationError(
                path=ctx.path,
                expected=_annotation_label(shape),
                actual=describe_ndarray(value),
                details=f"dimension {index} expected {expected_dim}, got {actual_int}; {_symbol_details(ctx) or 'no symbol bindings'}",
                context=dict(ctx.symbols),
            )


def _validate_ndarray_dtype(value: Any, annotation: DTypeAnnotation, ctx: Context) -> None:
    np = load_numpy()
    if np is None:
        raise ValidationError(
            path=ctx.path,
            expected=_annotation_label(annotation),
            actual=describe_ndarray(value),
            details="NumPy is not installed",
            context=dict(ctx.symbols),
        )

    try:
        expected_dtype = np.dtype(annotation.dtype_spec)
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(
            path=ctx.path,
            expected=_annotation_label(annotation),
            actual=describe_ndarray(value),
            details=f"invalid dtype specification: {exc}",
            context=dict(ctx.symbols),
        ) from exc

    actual_dtype = np.dtype(getattr(value, "dtype", None))
    if actual_dtype != expected_dtype:
        raise ValidationError(
            path=ctx.path,
            expected=_annotation_label(annotation),
            actual=describe_ndarray(value),
            details=f"dtype {actual_dtype} does not match {expected_dtype}",
            context=dict(ctx.symbols),
        )


def _symbol_details(ctx: Context) -> str | None:
    if not ctx.symbols:
        return None
    parts = []
    for name, value in ctx.symbols.items():
        source = ctx.symbol_sources.get(name)
        if source:
            parts.append(f"where {name} = {value} from {source}")
        else:
            parts.append(f"where {name} = {value}")
    return ", ".join(parts)


def _is_union(annotation: Any) -> bool:
    origin = get_origin(annotation)
    return origin in (Union, types.UnionType)


def _annotation_label(annotation: Any) -> str:
    if annotation is Any:
        return "Any"
    if annotation is None or annotation is type(None):
        return "None"
    if isinstance(annotation, Predicate):
        return annotation.expected_text()
    if isinstance(annotation, SizedAnnotation):
        return str(annotation)
    if isinstance(annotation, NDArrayAnnotation):
        return str(annotation)
    if isinstance(annotation, ShapeAnnotation):
        return str(annotation)
    if isinstance(annotation, DTypeAnnotation):
        return str(annotation)

    origin = get_origin(annotation)
    if origin is Annotated:
        base, *metadata = get_args(annotation)
        parts = [_annotation_label(base)]
        for meta in metadata:
            parts.append(_annotation_label(meta) if isinstance(meta, (Predicate, SizedAnnotation)) else repr(meta))
        return f"Annotated[{', '.join(parts)}]"
    if origin is Literal:
        options = ", ".join(repr(option) for option in get_args(annotation))
        return f"Literal[{options}]"
    if origin in (list, set, frozenset):
        args = get_args(annotation)
        if args:
            return f"{origin.__name__}[{_annotation_label(args[0])}]"
        return origin.__name__
    if origin is tuple:
        args = get_args(annotation)
        if len(args) == 2 and args[1] is Ellipsis:
            return f"tuple[{_annotation_label(args[0])}, ...]"
        if args:
            return f"tuple[{', '.join(_annotation_label(arg) for arg in args)}]"
        return "tuple"
    if origin is dict:
        args = get_args(annotation)
        if len(args) == 2:
            return f"dict[{_annotation_label(args[0])}, {_annotation_label(args[1])}]"
        return "dict"
    if origin in (Union, types.UnionType):
        return " | ".join(_annotation_label(arg) for arg in get_args(annotation))
    if isinstance(annotation, type):
        return annotation.__name__
    return repr(annotation)
