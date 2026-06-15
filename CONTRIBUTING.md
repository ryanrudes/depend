# Contributing

## Setup

- Install the repo hooks with `bash scripts/install-git-hooks.sh`
- Sync dependencies with `uv sync --group dev`
- Read `agents/AGENTS.md` before touching runtime, docs, or plugin behavior

## Validation

Run the same checks the repo uses in hooks and CI:

- `bash agents/hooks/preflight.sh`
- `uv run pytest -q`
- `uv run mypy .`
- `uv run python -m compileall -q src tests`
- `bash agents/hooks/check-mypy-fixtures.sh`

## Pull requests

Use the pull request template and keep changes scoped. Runtime changes should land before static-plugin follow-up when both are needed.
