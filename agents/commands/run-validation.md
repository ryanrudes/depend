# Command: Run Validation

Run all available validation commands.

```bash
agents/hooks/preflight.sh
uv run pytest -q
uv run mypy .
uv run python -m compileall -q src tests
```

If a command fails because tooling has not been bootstrapped yet, report that clearly instead of pretending the void was intentional.
