from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Callable, cast

from .context import Context
from .errors import ValidationError, summarize_value


@dataclass(frozen=True, slots=True)
class Predicate:
    fn: Callable[..., bool]
    name: str
    message: str | None = None
    dependencies: tuple[str, ...] = ()
    static_kind: str | None = None
    static_args: tuple[Any, ...] = ()

    def expected_text(self) -> str:
        if self.message is None:
            return self.name
        return f"{self.name}: {self.message}"

    def validate(self, value: Any, ctx: Context) -> None:
        dependency_values: list[Any] = []
        missing_dependencies: list[str] = []
        for dependency in self.dependencies:
            if dependency not in ctx.values:
                missing_dependencies.append(dependency)
            else:
                dependency_values.append(ctx.values[dependency])

        if missing_dependencies:
            raise ValidationError(
                path=ctx.path,
                expected=self.expected_text(),
                actual=summarize_value(value),
                details=f"missing dependency {', '.join(missing_dependencies)}",
                context=dict(ctx.symbols),
            )

        try:
            passed = self.fn(value, *dependency_values)
        except Exception as exc:  # noqa: BLE001
            raise ValidationError(
                path=ctx.path,
                expected=self.expected_text(),
                actual=summarize_value(value),
                details=f"predicate raised {exc.__class__.__name__}: {exc}",
                context=dict(ctx.symbols),
            ) from exc

        if not bool(passed):
            raise ValidationError(
                path=ctx.path,
                expected=self.expected_text(),
                actual=summarize_value(value),
                context=dict(ctx.symbols),
            )


def where(
    fn: Callable[..., bool],
    message: str | None = None,
    *,
    name: str | None = None,
    dependencies: tuple[str, ...] = (),
) -> Predicate:
    predicate_name = name if name is not None else cast(str, getattr(fn, "__name__", "predicate"))
    return Predicate(
        fn=fn,
        name=predicate_name,
        message=message,
        dependencies=dependencies,
        static_kind=None,
        static_args=(),
    )


def predicate(
    fn: Callable[..., bool],
    message: str | None = None,
    *,
    name: str | None = None,
    dependencies: tuple[str, ...] = (),
) -> Predicate:
    return where(fn, message=message, name=name, dependencies=dependencies)


class GreaterThan:
    def __class_getitem__(cls, bound: Any) -> Predicate:
        return Predicate(
            fn=lambda value, threshold=bound: value > threshold,
            name=f"GreaterThan[{bound!r}]",
            message=f"must be greater than {bound}",
            static_kind="gt",
            static_args=(bound,),
        )


class GreaterEqual:
    def __class_getitem__(cls, bound: Any) -> Predicate:
        return Predicate(
            fn=lambda value, threshold=bound: value >= threshold,
            name=f"GreaterEqual[{bound!r}]",
            message=f"must be greater than or equal to {bound}",
            static_kind="ge",
            static_args=(bound,),
        )


class LessThan:
    def __class_getitem__(cls, bound: Any) -> Predicate:
        return Predicate(
            fn=lambda value, threshold=bound: value < threshold,
            name=f"LessThan[{bound!r}]",
            message=f"must be less than {bound}",
            static_kind="lt",
            static_args=(bound,),
        )


class LessEqual:
    def __class_getitem__(cls, bound: Any) -> Predicate:
        return Predicate(
            fn=lambda value, threshold=bound: value <= threshold,
            name=f"LessEqual[{bound!r}]",
            message=f"must be less than or equal to {bound}",
            static_kind="le",
            static_args=(bound,),
        )


class Between:
    def __class_getitem__(cls, bounds: Any) -> Predicate:
        if not isinstance(bounds, tuple) or len(bounds) != 2:
            raise TypeError("Between[...] expects two bounds")
        lo, hi = bounds
        return Predicate(
            fn=lambda value, lower=lo, upper=hi: lower <= value <= upper,
            name=f"Between[{lo!r}, {hi!r}]",
            message=f"must be between {lo} and {hi}",
            static_kind="between",
            static_args=(lo, hi),
        )


NonEmpty = Predicate(
    fn=lambda value: len(value) > 0,
    name="NonEmpty",
    message="must be non-empty",
    static_kind="non_empty",
    static_args=(),
)

Finite = Predicate(
    fn=lambda value: math.isfinite(value),
    name="Finite",
    message="must be finite",
    static_kind="finite",
    static_args=(),
)

Probability = Predicate(
    fn=lambda value: math.isfinite(value) and 0.0 <= value <= 1.0,
    name="Probability",
    message="must be between 0 and 1",
    static_kind="probability",
    static_args=(),
)

StrictlyIncreasing = Predicate(
    fn=lambda values: all(left < right for left, right in zip(values, values[1:])),
    name="StrictlyIncreasing",
    message="must be strictly increasing",
    static_kind="strictly_increasing",
    static_args=(),
)
