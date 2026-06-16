# mypy plugin

The plugin is optional. Runtime validation works without it, but the plugin gives `Annotated[...]` refinements a static assist.

## Setup

Add a mypy config such as:

```ini
[mypy]
python_version = 3.12
plugins = depend.mypy_plugin.plugin
mypy_path = src
show_error_codes = True
```

If `depend` is installed in your environment as a dependency, that is enough for mypy to import the plugin. You only need `mypy_path = src` when you are checking the source tree in this repository or another editable checkout of `depend`.

## What it currently understands

- `Annotated[T, GreaterThan[...]]`, `Between[...]`, `NonEmpty`, `Finite`, `Probability`, and `StrictlyIncreasing`
- `ensure(value, PositiveInt)` style narrowing
- `@checked` argument checking for functions using the structured metadata above

## What it does not do

- prove arbitrary `where(lambda ...)` predicates statically
- solve general Python logic
- infer every `Sized` or NumPy shape relationship

## Example

```python
from typing import Annotated

from depend import GreaterThan, checked, ensure

type PositiveInt = Annotated[int, GreaterThan[0]]

@checked
def f(x: PositiveInt) -> None:
    pass

def get_int() -> int:
    return -1

f(ensure(get_int(), PositiveInt))
```

The plugin can reject obvious literal mismatches such as `f(-1)` when the structured metadata is visible.

If you want VS Code hover text for the computed depend type itself, use the local hover bridge described in `vscode-hover.md`.
