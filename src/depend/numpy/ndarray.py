from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import Any

from .dtype import DTypeAnnotation
from .shape import ShapeAnnotation


@dataclass(frozen=True, slots=True)
class NDArrayAnnotation:
    shape: ShapeAnnotation
    dtype: DTypeAnnotation | None = None

    def __str__(self) -> str:
        if self.dtype is None:
            return f"NDArray[{self.shape}]"
        return f"NDArray[{self.shape}, {self.dtype}]"


class NDArray:
    def __class_getitem__(cls, item: Any) -> NDArrayAnnotation:
        if not isinstance(item, tuple) or len(item) != 2:
            raise TypeError("NDArray[...] expects a Shape[...] and a DType[...]")
        shape, dtype = item
        if not isinstance(shape, ShapeAnnotation):
            raise TypeError("NDArray[...] expects the first item to be a Shape[...] annotation")
        if dtype is not None and not isinstance(dtype, DTypeAnnotation):
            raise TypeError("NDArray[...] expects the second item to be a DType[...] annotation")
        return NDArrayAnnotation(shape=shape, dtype=dtype)


def load_numpy() -> ModuleType | None:
    try:
        import numpy as np  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return None
    return np


def describe_ndarray(value: Any) -> str:
    shape = getattr(value, "shape", None)
    dtype = getattr(value, "dtype", None)
    return f"ndarray shape={shape} dtype={dtype}"
