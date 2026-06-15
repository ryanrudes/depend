# Command: Bootstrap Project

Use when creating the initial `depend` project.

## Steps

1. Create `pyproject.toml` with uv + hatchling + Python 3.12+.
2. Create `src/depend/` package layout.
3. Create `tests/runtime/` and `tests/mypy/` layout.
4. Add minimal pytest config.
5. Add mypy config with plugin disabled until plugin exists.
6. Run preflight.

## Required pyproject invariants

```toml
[project]
requires-python = ">=3.12"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```
