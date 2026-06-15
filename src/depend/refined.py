from __future__ import annotations

from dataclasses import replace
from typing import Any, Annotated, Callable

from .predicates import Predicate, where


def refined(
    base: type[Any],
    predicate: Callable[[Any], bool] | Predicate,
    *,
    name: str | None = None,
    message: str | None = None,
) -> Any:
    if isinstance(predicate, Predicate):
        refined_predicate = predicate
        if name is not None or message is not None:
            refined_predicate = replace(
                refined_predicate,
                name=name or refined_predicate.name,
                message=message if message is not None else refined_predicate.message,
            )
    else:
        refined_predicate = where(predicate, message=message, name=name)

    return Annotated[base, refined_predicate]
