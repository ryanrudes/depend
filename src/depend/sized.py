from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .expressions import Expr, format_expr, parse_expr


@dataclass(frozen=True, slots=True)
class SizedAnnotation:
    container_annotation: Any
    length_expr: Expr

    def __str__(self) -> str:
        return f"Sized[{self.container_annotation!r}, {format_expr(self.length_expr)}]"


class Sized:
    def __class_getitem__(cls, item: Any) -> SizedAnnotation:
        if not isinstance(item, tuple) or len(item) != 2:
            raise TypeError("Sized[...] expects a container annotation and a length expression")
        container_annotation, length_expr = item
        return SizedAnnotation(container_annotation=container_annotation, length_expr=parse_expr(length_expr))
