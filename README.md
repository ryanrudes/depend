# depend

[![CI](https://github.com/ryanrudes/depend/actions/workflows/ci.yml/badge.svg)](https://github.com/ryanrudes/depend/actions/workflows/ci.yml)
[![Docs](https://github.com/ryanrudes/depend/actions/workflows/pages.yml/badge.svg)](https://github.com/ryanrudes/depend/actions/workflows/pages.yml)
[![GitHub Pages](https://img.shields.io/badge/docs-GitHub%20Pages-2a6fbb)](https://ryanrudes.github.io/depend/)

`depend` provides dependent-style typing for Python: runtime-validated, statically assisted, and built around structured predicates.

It is designed for ordinary Python code that needs more shape than `Any` but should still run normally without a custom checker.

## Highlights

- refinements with `Predicate` and `where`
- `@checked` runtime validation for arguments and returns
- `Sized` symbolic lengths
- NumPy shape and dtype annotations
- proof objects for validated values
- registry metadata for structured hierarchies
- an optional mypy plugin for structured predicates

## Docs

- Live site: [https://ryanrudes.github.io/depend/](https://ryanrudes.github.io/depend/)
- Build the site with `uv run mkdocs build`
- Serve it locally with `uv run mkdocs serve`
- Read the topic pages in `docs/`

## Repository setup

- Create the local dev environment with `uv sync --group dev`
- Install the repo hooks with `bash scripts/install-git-hooks.sh`
- Run the validation bundle with `agents/hooks/preflight.sh`, `uv run pytest -q`, `uv run mypy .`, and `uv run python -m compileall -q src tests`
- Use `docs/` as the MkDocs source and `site/` as the generated output

## VS Code setup for this checkout

VS Code uses two separate integrations here:

- the Problems pane is driven by `mypy` with `tests/mypy.ini`
- hover text comes from the local `editor/depend-hover` extension

The repository ships `.vscode/settings.json` with the expected defaults. If you want to set it up manually, use these steps:

1. Open the repository root in VS Code.
2. Install the `mypy-type-checker` extension so the Problems pane runs `mypy`.
3. Run `Developer: Install Extension from Location...` and choose `editor/depend-hover`.
4. Reload VS Code.
5. Make sure the workspace uses `tests/mypy.ini` for both the mypy checker and the hover bridge.

```json
{
  "mypy-type-checker.importStrategy": "fromEnvironment",
  "mypy-type-checker.interpreter": ["${workspaceFolder}/.venv/bin/python"],
  "mypy-type-checker.args": ["--config-file", "${workspaceFolder}/tests/mypy.ini"],
  "mypy-type-checker.cwd": "${workspaceFolder}",
  "mypy-type-checker.reportingScope": "file",
  "mypy-type-checker.preferDaemon": false,
  "dependHover.mypyConfig": "${workspaceFolder}/tests/mypy.ini",
  "dependHover.scriptPath": "${workspaceFolder}/scripts/hover_type.py",
  "dependHover.pythonCommand": "uv",
  "dependHover.timeoutMs": 4000,
  "python.analysis.extraPaths": ["${workspaceFolder}/src"]
}
```

The built-in Python hover providers do not read mypy plugins, so the hover bridge is the piece that shows the computed depend type itself. The mypy checker is what keeps the Problems pane aligned with the same plugin config.

## Using depend in another project

If your own project installs `depend` as a dependency, the setup is slightly different:

1. Add `depend` to your runtime dependencies.
2. Add `mypy` to your dev dependencies.
3. In your project's mypy config, enable `plugins = depend.mypy_plugin.plugin`.
4. Install `mypy-type-checker` in VS Code so the Problems pane runs your mypy config.
5. Install the local `depend-hover` extension from `editor/depend-hover` in a checkout of this repository, or copy that folder into the consumer workspace and install it from there, then point it at the helper script and mypy config used by that project.

For a consumer project, the mypy config usually looks like this:

```ini
[mypy]
python_version = 3.12
plugins = depend.mypy_plugin.plugin
show_error_codes = True
```

And the workspace settings should point both integrations at the consumer project, not this repository:

```json
{
  "mypy-type-checker.importStrategy": "fromEnvironment",
  "mypy-type-checker.interpreter": ["${workspaceFolder}/.venv/bin/python"],
  "mypy-type-checker.args": ["--config-file", "${workspaceFolder}/mypy.ini"],
  "mypy-type-checker.cwd": "${workspaceFolder}",
  "mypy-type-checker.reportingScope": "file",
  "mypy-type-checker.preferDaemon": false,
  "dependHover.mypyConfig": "${workspaceFolder}/mypy.ini",
  "dependHover.scriptPath": "/path/to/depend/scripts/hover_type.py",
  "dependHover.pythonCommand": "uv",
  "dependHover.timeoutMs": 4000
}
```

If you vendor the hover helper into your own project, change `dependHover.scriptPath` to that copy instead. The Problems pane still comes from mypy, and the hover popup still comes from the local bridge.

## Examples

Runnable examples live in `examples/`.
