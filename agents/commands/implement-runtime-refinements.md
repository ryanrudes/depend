# Command: Implement Runtime Refinements

Build the first runtime slice.

## Deliverables

- `Predicate`
- `where`
- `refined`
- `validate`
- `ensure`
- `is_valid`
- `ValidationError`
- tests for all of the above

## Acceptance examples

```python
PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")
validate(3, PositiveInt)
validate(-1, PositiveInt)  # raises ValidationError
```

```python
x = ensure(5, PositiveInt)
assert x == 5
```

## Validation

```bash
uv run pytest tests/runtime/test_refined.py -q
uv run python -m compileall -q src tests
```
