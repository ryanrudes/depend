# VS Code hover

VS Code hover text does not come from mypy plugins directly. Pylance and the mypy plugin are separate systems, so the plugin can validate code without affecting the built-in hover provider.

To get computed `depend` types on hover in this repository, use the local hover bridge in `editor/depend-hover/`. The bridge uses `dmypy inspect` with the repo's mypy config to ask `mypy` for the expression type at the cursor, then shows the plugin-specific refinement or source annotation as the secondary line when that is more informative.
It also surfaces matching mypy diagnostics from the current line so the hover explains both the computed type and the nearby problem.
The extension keeps a warm Python helper process alive per workspace/config and prefetches hover results in the background on cursor movement, so the hover popup itself stays instant once a token has been warmed. Results are cached in memory per file version until the file changes.

## What it shows

- `type` aliases like `type PositiveInt = Annotated[int, GreaterThan[0]]`
- expression results such as `parent_of(RuntimeFragments.VALIDATE)` and `label_of(...)`
- registered members like `RuntimeFragments.VALIDATE`
- bindings created with `ensure(value, Annotation)`
- parameters and other names via the current inferred type in the hovered block
- the current line's matching mypy problems, when present

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

- The bridge is best-effort and still depends on the file on disk, so unsaved buffer changes are not reflected.
- It does not replace Pylance or mypy.
- It relies on the repo's `tests/mypy.ini` so the plugin hooks stay enabled.
