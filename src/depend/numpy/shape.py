from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..expressions import Expr, parse_expr


class AnyDimType:
    def __repr__(self) -> str:
        return "AnyDim"


AnyDim = AnyDimType()


@dataclass(frozen=True, slots=True)
class ShapeAnnotation:
    dims: tuple[Expr | AnyDimType, ...]

    def __str__(self) -> str:
        parts = []
        for dim in self.dims:
            parts.append("AnyDim" if dim is AnyDim else str(dim))
        return f"Shape[{', '.join(parts)}]"


class Shape:
    def __class_getitem__(cls, item: Any) -> ShapeAnnotation:
        if not isinstance(item, tuple):
            item = (item,)

        dims: list[Expr | AnyDimType] = []
        for dim in item:
            if dim is AnyDim:
                dims.append(AnyDim)
            else:
                dims.append(parse_expr(dim))
        return ShapeAnnotation(tuple(dims))
