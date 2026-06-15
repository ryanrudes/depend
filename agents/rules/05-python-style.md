# Rule: Python Style, Packaging, and Typing

## Packaging

This project is packaged with `uv` and uses Hatch / `hatchling` as the build backend.

Required `pyproject.toml` invariants:

```toml
[project]
requires-python = ">=3.12"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Do not add Poetry, Pipenv, PDM, Flit, setuptools-only configuration, or conda environment assumptions.

## Python version

Support Python 3.12+ only. Do not add compatibility shims for Python 3.11 or older.

## Typing style

Use modern Python typing.

Prefer PEP 695 syntax:

```python
class Box[T]:
    value: T


def first[T](items: Sequence[T]) -> T:
    return items[0]

type JsonScalar = str | int | float | bool | None
```

Avoid legacy `TypeVar`-heavy patterns unless:

- mypy plugin APIs require it;
- runtime generic machinery cannot express the type with PEP 695;
- compatibility with a third-party type stub requires it.

## Imports

Prefer:

```python
from collections.abc import Callable, Mapping, Sequence
```

over older `typing` collection aliases.

## Formatting

Use straightforward Python. Avoid clever metaclasses, import hooks, and spooky decorator behavior. The library already does type magic; the implementation should not look like it was written during a lightning storm.
