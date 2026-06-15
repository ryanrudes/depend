# Registries

`register(...)` records parent-child metadata for classes and enum-like values. The registry helpers are small but useful when you need structured labels and hierarchy lookups.

- `parent_of(item)` returns the registered parent
- `children_of(parent)` returns registered children
- `label_of(item)` returns the stable display label

## Example

```python
from enum import Enum

from depend import children_of, label_of, parent_of, register

class Topics(Enum):
    RUNTIME = "runtime"
    STATIC = "static"

@register(to=Topics.RUNTIME)
class RuntimeFragments:
    VALIDATE = "validate"
    CHECKED = "checked"

assert label_of(Topics.RUNTIME) == "runtime"
assert label_of(RuntimeFragments.VALIDATE) == "runtime:validate"
assert parent_of(RuntimeFragments.VALIDATE) == Topics.RUNTIME
assert set(children_of(Topics.RUNTIME)) == {"validate", "checked"}
```

