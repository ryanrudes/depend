# NumPy shapes

`NDArray[Shape[..., ...], DType[...]]` describes array rank, dimension expressions, and dtype expectations. `AnyDim` is a wildcard dimension.

Validation is lazy. NumPy is imported only when you validate an array annotation, so the runtime remains usable when NumPy is absent.

The current mypy plugin does not try to prove array shapes statically. Runtime validation is still authoritative.

## Example

```python
from depend import AnyDim, Float64, NDArray, Shape, ValidationError, checked

@checked
def normalize_rows(x: NDArray[Shape["n", 3], Float64]) -> NDArray[Shape["n", 3], Float64]:
    return x

@checked
def passthrough(x: NDArray[Shape["n", AnyDim], Float64]) -> NDArray[Shape["n", AnyDim], Float64]:
    return x

try:
    import numpy as np
except ModuleNotFoundError:
    np = None

if np is not None:
    arr = np.ones((2, 3), dtype=np.float64)
    assert normalize_rows(arr).shape == (2, 3)
    assert passthrough(np.ones((2, 5), dtype=np.float64)).shape == (2, 5)

    try:
        normalize_rows(np.ones((2, 2), dtype=np.float64))
    except ValidationError:
        pass
```

