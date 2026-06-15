# Command: Implement @checked

Add explicit function contract validation.

## Deliverables

- `@checked`
- sync and async support
- argument validation
- return validation
- disabled checks via decorator option
- disabled checks via `DEPEND_DISABLE_CHECKS=1`
- tests

## Acceptance examples

```python
@checked
def f(x: PositiveInt) -> PositiveInt:
    return x

f(-1)  # raises ValidationError
```

```python
@checked
def bad(x: PositiveInt) -> PositiveInt:
    return -1

bad(1)  # raises on return
```
