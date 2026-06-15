# depend

`depend` provides dependent-style typing for Python: runtime-validated, statically assisted, and built around structured predicates.

The library keeps the runtime honest and uses mypy as a useful but incomplete assistant. It is not a complete theorem prover, and it does not try to turn arbitrary Python into logic.

The documentation is built with MkDocs and published to GitHub Pages from this repository.

## Quick start

```python
from depend import GreaterThan, checked, refined, validate

PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")

@checked
def repeat(text: str, n: PositiveInt) -> str:
    return text * n

assert validate(3, PositiveInt) == 3
assert repeat("ha", 3) == "hahaha"
```

## What to read next

- `refinements.md` for `Predicate`, `where`, and known predicates
- `checked-functions.md` for `@checked`, `ensure`, and return validation
- `sized-collections.md` for symbolic lengths
- `numpy-shapes.md` for array shapes and dtypes
- `proofs.md` for proof objects and proof requirements
- `registries.md` for registry metadata
- `mypy-plugin.md` for plugin setup
- `limitations.md` for the edges of the system
