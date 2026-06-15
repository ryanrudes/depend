# VS Code hover

VS Code hover text does not come from mypy plugins directly. Pylance and the mypy plugin are separate systems, so the plugin can validate code without affecting the built-in hover provider.

To get computed `depend` types on hover in this repository, use the local hover bridge in `editor/depend-hover/`.

## What it shows

- `type` aliases like `type PositiveInt = Annotated[int, GreaterThan[0]]`
- parameters annotated with `PositiveInt`, `Sized[...]`, or `NDArray[...]`
- bindings created with `ensure(value, Annotation)`
- `refined(...)` aliases by alias name

## Install

1. Open the repository in VS Code.
2. Run `Developer: Install Extension from Location...`
3. Choose `editor/depend-hover`
4. Reload the window

## Settings

The extension assumes:

- `uv` is available on `PATH`
- the repo uses `tests/mypy.ini`

You can override those defaults with workspace settings:

```json
{
  "dependHover.mypyConfig": "${workspaceFolder}/tests/mypy.ini",
  "dependHover.pythonCommand": "uv",
  "dependHover.timeoutMs": 4000
}
```

## Limitations

- The bridge is best-effort and file-local.
- It does not replace Pylance or mypy.
- It does not yet provide full flow-sensitive narrowing for arbitrary control flow.
