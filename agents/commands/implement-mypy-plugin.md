# Command: Implement mypy Plugin MVP

Add the first static support layer.

## Deliverables

- plugin entry point `depend.mypy_plugin.plugin`
- mypy config docs
- hook for `ensure(...)`
- basic known predicate literal checks
- mypy fixture tests

## Requirements

Do not execute arbitrary predicates in mypy.

Known predicates may be checked statically. Runtime-only predicates must remain runtime-only.

## Acceptance examples

```python
PositiveInt = Annotated[int, GreaterThan[0]]

@checked
def f(x: PositiveInt) -> None:
    ...

f(-1)  # mypy error
```

```python
x = ensure(get_int(), PositiveInt)
f(x)  # accepted
```
