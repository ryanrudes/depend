from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from typing import Annotated, get_args, get_origin

from .context import Context
from .errors import ValidationError, summarize_value
from .predicates import Predicate
from .sized import SizedAnnotation


@dataclass(frozen=True, slots=True)
class Proof:
    value_id: int
    annotation_fingerprint: str
    predicate_name: str


@dataclass(frozen=True, slots=True)
class RequiresProofAnnotation:
    value_name: str
    annotation: Any

    def __str__(self) -> str:
        return f"RequiresProof[{self.value_name!r}, {self.annotation!r}]"


class RequiresProof:
    def __class_getitem__(cls, item: Any) -> RequiresProofAnnotation:
        if not isinstance(item, tuple) or len(item) != 2:
            raise TypeError("RequiresProof[...] expects a value name and an annotation")
        value_name, annotation = item
        if not isinstance(value_name, str):
            raise TypeError("RequiresProof[...] requires the first item to be a string value name")
        return RequiresProofAnnotation(value_name=value_name, annotation=annotation)


def prove(value: Any, annotation: Any) -> Proof:
    from .validate import validate

    validate(value, annotation)
    return Proof(
        value_id=id(value),
        annotation_fingerprint=annotation_fingerprint(annotation),
        predicate_name=annotation_name(annotation),
    )


@contextmanager
def ensured(value: Any, annotation: Any):
    from .validate import validate

    validate(value, annotation)
    yield value


def annotation_fingerprint(annotation: Any) -> str:
    return repr(annotation)


def annotation_name(annotation: Any) -> str:
    if isinstance(annotation, Predicate):
        return annotation.name

    origin = get_origin(annotation)
    if origin is Annotated:
        base, *metadata = get_args(annotation)
        for meta in metadata:
            if isinstance(meta, Predicate):
                return meta.name
        return annotation_name(base)

    if isinstance(annotation, SizedAnnotation):
        return str(annotation)

    if hasattr(annotation, "__name__"):
        return str(annotation.__name__)
    return repr(annotation)


def validate_requires_proof(value: Any, annotation: RequiresProofAnnotation, ctx: Context) -> None:
    if not isinstance(value, Proof):
        raise ValidationError(
            path=ctx.path,
            expected=f"proof for {annotation.value_name}",
            actual=summarize_value(value),
            details="expected a Proof instance",
            context=dict(ctx.symbols),
        )

    if annotation.value_name not in ctx.values:
        raise ValidationError(
            path=ctx.path,
            expected=f"proof for {annotation.value_name}",
            actual=summarize_value(value),
            details=f"missing value {annotation.value_name!r} in validation context",
            context=dict(ctx.symbols),
        )

    target_value = ctx.values[annotation.value_name]
    expected_fingerprint = annotation_fingerprint(annotation.annotation)
    expected_name = annotation_name(annotation.annotation)
    expected_value_id = id(target_value)

    mismatches: list[str] = []
    if value.value_id != expected_value_id:
        mismatches.append(f"value id {value.value_id} does not match id({annotation.value_name}) = {expected_value_id}")
    if value.annotation_fingerprint != expected_fingerprint:
        mismatches.append(
            f"annotation fingerprint {value.annotation_fingerprint!r} does not match {expected_fingerprint!r}"
        )
    if value.predicate_name != expected_name:
        mismatches.append(f"predicate name {value.predicate_name!r} does not match {expected_name!r}")

    if mismatches:
        raise ValidationError(
            path=ctx.path,
            expected=f"proof for {annotation.value_name}",
            actual=summarize_value(value),
            details="; ".join(mismatches),
            context=dict(ctx.symbols),
        )

    ctx.proofs[(annotation.value_name, value.value_id, value.annotation_fingerprint)] = value
