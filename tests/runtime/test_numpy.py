from __future__ import annotations

import pytest

from depend import AnyDim, Float64, NDArray, Shape, ValidationError, checked


def test_ndarray_shape_and_dtype_validation() -> None:
    np = pytest.importorskip("numpy")

    @checked
    def normalize_rows(x: NDArray[Shape["n", 3], Float64]) -> NDArray[Shape["n", 3], Float64]:
        return x

    arr = np.ones((2, 3), dtype=np.float64)
    assert normalize_rows(arr) is arr

    with pytest.raises(ValidationError):
        normalize_rows(np.ones((2, 2), dtype=np.float64))

    with pytest.raises(ValidationError):
        normalize_rows(np.ones((2, 3), dtype=np.float32))


def test_ndarray_symbol_binding_across_arguments() -> None:
    np = pytest.importorskip("numpy")

    @checked
    def add_rows(
        a: NDArray[Shape["n", 3], Float64],
        b: NDArray[Shape["n", 3], Float64],
    ) -> NDArray[Shape["n", 3], Float64]:
        return a + b

    assert add_rows(np.ones((2, 3), dtype=np.float64), np.ones((2, 3), dtype=np.float64)).shape == (2, 3)

    with pytest.raises(ValidationError):
        add_rows(np.ones((2, 3), dtype=np.float64), np.ones((3, 3), dtype=np.float64))


def test_anydim_wildcard_dimension() -> None:
    np = pytest.importorskip("numpy")

    @checked
    def passthrough(x: NDArray[Shape["n", AnyDim], Float64]) -> NDArray[Shape["n", AnyDim], Float64]:
        return x

    assert passthrough(np.ones((2, 5), dtype=np.float64)).shape == (2, 5)
