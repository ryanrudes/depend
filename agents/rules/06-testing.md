# Rule: Testing

Every feature needs runtime tests. Static plugin features also need mypy integration tests.

## Runtime tests

Use pytest for:

- predicates
- refinements
- validation engine
- `@checked`
- `Sized`
- symbolic expressions
- NumPy shapes
- dataclasses
- proofs
- registry metadata
- error messages

## mypy plugin tests

Create fixture files under `tests/mypy/cases/` and run mypy programmatically or through subprocess.

Test both success and failure cases.

Examples:

```python
f(-1)  # E: violates GreaterThan[0]
```

## Required validation before handoff

Run what applies:

```bash
uv run pytest -q
uv run mypy .
uv run python -m compileall -q src tests
agents/hooks/preflight.sh
```

If unavailable, report the exact failure.
