# Checked functions

`@checked` wraps sync and async callables and validates arguments before the function body runs. It also validates return values unless you disable return checking.

`ensure(value, annotation)` is the inline validation helper. It returns the original value after checking it.

Checks can be disabled with `DEPEND_DISABLE_CHECKS=1`.

## Example

```python
from depend import ValidationError, checked, ensure, refined

PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")

@checked
def repeat(text: str, n: PositiveInt) -> str:
    return text * n

@checked
def broken(n: PositiveInt) -> PositiveInt:
    return -n

assert repeat("ha", ensure(3, PositiveInt)) == "hahaha"

try:
    repeat("ha", -1)
except ValidationError:
    pass
```

