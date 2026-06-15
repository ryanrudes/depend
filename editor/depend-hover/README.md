# depend Hover

This local VS Code extension shows computed `depend` types on hover by calling the repo helper in `scripts/hover_type.py`.

## Install locally

1. Open VS Code on the repository root.
2. Run `Developer: Install Extension from Location...`
3. Choose `editor/depend-hover`
4. Reload VS Code

## Configure

The default settings assume:

- `uv` is on `PATH`
- the repo uses `tests/mypy.ini`

You can override the config in workspace settings:

```json
{
  "dependHover.mypyConfig": "${workspaceFolder}/tests/mypy.ini",
  "dependHover.pythonCommand": "uv",
  "dependHover.timeoutMs": 4000
}
```
