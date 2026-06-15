from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DTypeAnnotation:
    dtype_spec: Any

    def __str__(self) -> str:
        return f"DType[{_format_dtype_spec(self.dtype_spec)}]"


class DType:
    def __class_getitem__(cls, item: Any) -> DTypeAnnotation:
        return DTypeAnnotation(item)


def _dtype_alias(spec: Any) -> DTypeAnnotation:
    return DTypeAnnotation(spec)


Float32 = _dtype_alias("float32")
Float64 = _dtype_alias("float64")
Int32 = _dtype_alias("int32")
Int64 = _dtype_alias("int64")
Bool = _dtype_alias("bool")


def _format_dtype_spec(spec: Any) -> str:
    if isinstance(spec, str):
        return spec

    name = getattr(spec, "__name__", None)
    module = getattr(spec, "__module__", None)
    if name and module == "numpy":
        return f"np.{name}"
    return repr(spec)
