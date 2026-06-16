# depend Hover

This local VS Code extension shows computed `depend` types on hover by calling the repo helper in `scripts/hover_type.py` by default.
The helper uses `dmypy inspect` against the repo's mypy config to ask `mypy` for the type of the expression under the cursor, then shows the plugin-specific refinement as the secondary line when it differs.
The hover popup also surfaces matching mypy diagnostics from the current line so problems such as invalid `validate(...)` calls are visible in the same place as the type info.
The extension keeps a warm Python helper process alive per workspace/config and prefetches hover results in the background on cursor movement, so the hover popup itself stays instant once a token has been warmed. Results are cached in memory per file version until you edit the file.

## Install locally

1. Open VS Code on the repository root.
2. Run `Developer: Install Extension from Location...`
3. Choose `editor/depend-hover`
4. Reload VS Code

## Configure

The default settings assume:

- `uv` is on `PATH`
- the repo uses `tests/mypy.ini`
- the helper script lives at `${workspaceFolder}/scripts/hover_type.py`

You can override the config in workspace settings:

```json
{
  "dependHover.mypyConfig": "${workspaceFolder}/tests/mypy.ini",
  "dependHover.scriptPath": "${workspaceFolder}/scripts/hover_type.py",
  "dependHover.pythonCommand": "uv",
  "dependHover.timeoutMs": 4000
}
```

For a downstream project that installs `depend` as a dependency, set `dependHover.mypyConfig` to that project's mypy config and `dependHover.scriptPath` to the helper script you want to run.

Hover results work best when the repo's `tests/mypy.ini` is used, since that enables the `depend.mypy_plugin.plugin` hooks for `validate`, `ensure`, registry helpers, and refined annotations.
