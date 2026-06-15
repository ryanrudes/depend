from __future__ import annotations

import inspect
import os
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast, get_type_hints, overload

from .context import Context
from .errors import ValidationError
from .validate import validate

P = ParamSpec("P")
R = TypeVar("R")


@overload
def checked(func: Callable[P, R], /) -> Callable[P, R]: ...


@overload
def checked(
    *,
    enabled: bool = True,
    validate_return: bool = True,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def checked(
    func: Callable[P, R] | None = None,
    /,
    *,
    enabled: bool = True,
    validate_return: bool = True,
) -> Callable[[Callable[P, R]], Callable[P, R]] | Callable[P, R]:
    def decorate(target: Callable[P, R]) -> Callable[P, R]:
        if not enabled or os.environ.get("DEPEND_DISABLE_CHECKS") == "1":
            return target

        signature = inspect.signature(target)
        try:
            hints = get_type_hints(target, include_extras=True)
        except Exception:  # noqa: BLE001
            hints = dict(target.__annotations__)

        if inspect.iscoroutinefunction(target):

            @wraps(target)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                context = Context(path=(target.__name__,))
                for name, value in bound.arguments.items():
                    context.bind_value(name, value)
                _validate_bound_arguments(signature, hints, bound.arguments, context)
                result = await target(*args, **kwargs)
                if validate_return:
                    return_annotation = hints.get("return", signature.return_annotation)
                    if return_annotation is not inspect.Signature.empty and return_annotation is not Any:
                        validate(result, return_annotation, context.child("return"))
                return result

            return cast(Callable[P, R], async_wrapper)

        @wraps(target)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            context = Context(path=(target.__name__,))
            for name, value in bound.arguments.items():
                context.bind_value(name, value)
            _validate_bound_arguments(signature, hints, bound.arguments, context)
            result = target(*args, **kwargs)
            if validate_return:
                return_annotation = hints.get("return", signature.return_annotation)
                if return_annotation is not inspect.Signature.empty and return_annotation is not Any:
                    validate(result, return_annotation, context.child("return"))
            return result

        return sync_wrapper

    if func is None:
        return decorate
    return decorate(func)


def _validate_bound_arguments(
    signature: inspect.Signature,
    hints: dict[str, Any],
    bound_arguments: dict[str, Any],
    context: Context,
) -> None:
    for name, parameter in signature.parameters.items():
        if name not in bound_arguments:
            continue

        annotation = hints.get(name, parameter.annotation)
        if annotation is inspect.Signature.empty or annotation is Any:
            continue

        value = bound_arguments[name]
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            for index, item in enumerate(value):
                validate(item, annotation, context.child(f"argument {name}[{index}]"))
            continue

        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            for key, item in value.items():
                validate(item, annotation, context.child(f"argument {name}.{key}"))
            continue

        validate(value, annotation, context.child(f"argument {name}"))
