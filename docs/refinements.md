# Refinements

`Predicate` is the core runtime refinement object. Use `refined(...)` for a convenient alias builder and `where(...)` when you want to describe a runtime-only predicate directly.

## Known predicates

The library ships a small structured set of predicates that the mypy plugin can recognize:

- `GreaterThan[0]`
- `GreaterEqual[0]`
- `LessThan[10]`
- `LessEqual[10]`
- `Between[0, 1]`
- `NonEmpty`
- `Finite`
- `Probability`
- `StrictlyIncreasing`

## Runtime-only predicates

`where(lambda x: expensive(x), "must satisfy the check")` is runtime-validated, but the plugin treats it as opaque. That is intentional: arbitrary Python code is not statically provable in general.

## Example

```python
from typing import Annotated

from depend import Between, GreaterThan, refined, validate, where

PositiveInt = Annotated[int, GreaterThan[0]]
OddInt = refined(int, lambda x: x % 2 == 1, name="OddInt")
Probability = Annotated[float, Between[0.0, 1.0]]
EvenInt = Annotated[int, where(lambda x: x % 2 == 0, "must be even")]

assert validate(3, PositiveInt) == 3
assert validate(0.25, Probability) == 0.25
assert validate(5, OddInt) == 5
```

