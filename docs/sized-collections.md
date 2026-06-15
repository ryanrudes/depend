# Sized collections

`Sized[container, expr]` validates the container and then checks that its length matches the expression. Expressions can be constants, symbols, or simple arithmetic such as `"n + 1"`.

When a symbol is first seen, it is bound to the observed length. Later uses of the same symbol must match.

## Example

```python
from depend import Context, Sized, ValidationError, checked, validate

annotation = Sized[list[int], "n"]
ctx = Context(path=("values",))

assert validate([1, 2, 3], annotation, ctx) == [1, 2, 3]
assert ctx.symbols["n"] == 3

@checked
def dot(a: Sized[list[int], "n"], b: Sized[list[int], "n"]) -> int:
    return sum(a) + sum(b)

assert dot([1, 2], [3, 4]) == 10

try:
    dot([1, 2], [3])
except ValidationError:
    pass
```

