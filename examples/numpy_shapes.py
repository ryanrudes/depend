from __future__ import annotations

from typing import Annotated, Any

from depend import AnyDim, Float64, NDArray, Shape, ValidationError, checked


Array3xFloat64 = Annotated[Any, NDArray[Shape["n", 3], Float64]]
ArrayAnyWidthFloat64 = Annotated[Any, NDArray[Shape["n", AnyDim], Float64]]


@checked
def normalize_rows(x: Array3xFloat64) -> Array3xFloat64:
    return x


@checked
def passthrough(x: ArrayAnyWidthFloat64) -> ArrayAnyWidthFloat64:
    return x


def main() -> None:
    try:
        import numpy as np  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        print("NumPy is not installed")
        return

    arr = np.ones((2, 3), dtype=np.float64)
    print(normalize_rows(arr).shape)
    print(passthrough(np.ones((2, 5), dtype=np.float64)).shape)

    try:
        normalize_rows(np.ones((2, 2), dtype=np.float64))
    except ValidationError as exc:
        print(exc)


if __name__ == "__main__":
    main()
