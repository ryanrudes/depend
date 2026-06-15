from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from functools import wraps
from typing import Any, Callable, TypeVar, cast, dataclass_transform, get_type_hints

from .context import Context
from .errors import ValidationError
from .validate import validate

T = TypeVar("T")


@dataclass_transform()
def checked_dataclass(
    cls: type[T] | None = None,
    /,
    *,
    validate_before_post_init: bool = False,
) -> Callable[[type[T]], type[T]] | type[T]:
    def decorate(target: type[T]) -> type[T]:
        if not is_dataclass(target):
            target = dataclass(target)

        try:
            hints = get_type_hints(target, include_extras=True)
        except Exception:  # noqa: BLE001
            hints = dict(target.__annotations__)

        dataclass_fields = tuple(fields(cast(Any, target)))
        original_post_init = getattr(target, "__post_init__", None)

        def validate_fields(instance: Any) -> None:
            context = Context(path=(target.__name__,))
            values: dict[str, Any] = {}
            for field in dataclass_fields:
                try:
                    value = getattr(instance, field.name)
                except AttributeError as exc:
                    annotation = hints.get(field.name, field.type)
                    raise ValidationError(
                        path=context.child(f"field {field.name}").path,
                        expected=_annotation_label(annotation),
                        actual="missing attribute",
                        details="dataclass field is not initialized",
                        context=dict(context.symbols),
                    ) from exc
                values[field.name] = value
                context.bind_value(field.name, value)

            for field in dataclass_fields:
                annotation = hints.get(field.name, field.type)
                validate(values[field.name], annotation, context.child(f"field {field.name}"))

        if original_post_init is not None:

            @wraps(original_post_init)
            def __post_init__(self: Any, *args: Any) -> None:
                if validate_before_post_init:
                    validate_fields(self)
                    original_post_init(self, *args)
                else:
                    original_post_init(self, *args)
                    validate_fields(self)

            setattr(target, "__post_init__", __post_init__)
            return target

        original_init = target.__init__

        @wraps(original_init)
        def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            validate_fields(self)

        setattr(target, "__init__", __init__)
        return target

    if cls is None:
        return decorate
    return decorate(cls)


def _annotation_label(annotation: Any) -> str:
    if hasattr(annotation, "__name__"):
        return str(annotation.__name__)
    return repr(annotation)


@dataclass_transform()
def dependent_dataclass(
    cls: type[T] | None = None,
    /,
    **dataclass_kwargs: Any,
) -> Callable[[type[T]], type[T]] | type[T]:
    def decorate(target: type[T]) -> type[T]:
        if is_dataclass(target):
            return cast(type[T], checked_dataclass(target))
        return cast(type[T], checked_dataclass(dataclass(**dataclass_kwargs)(target)))

    if cls is None:
        return decorate
    return decorate(cls)
