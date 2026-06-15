from __future__ import annotations

from depend import AnyDim, Float64, NDArray, Shape, ValidationError, checked


@checked
def normalize_rows(x: NDArray[Shape["n", 3], Float64]) -> NDArray[Shape["n", 3], Float64]:
    return x


@checked
def passthrough(x: NDArray[Shape["n", AnyDim], Float64]) -> NDArray[Shape["n", AnyDim], Float64]:
    return x


def main() -> None:
    try:
        import numpy as np
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

