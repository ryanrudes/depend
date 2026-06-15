# Command: Implement Sized

Add symbolic length constraints.

## Deliverables

- restricted expression parser
- `Expr` model
- `Context` symbol binding
- `Sized`
- runtime validation
- return validation with same context
- tests

## Acceptance examples

```python
@checked
def dot(a: Sized[list[float], "n"], b: Sized[list[float], "n"]) -> float:
    return sum(x * y for x, y in zip(a, b))

 dot([1, 2], [3, 4])  # ok
 dot([1, 2], [3])     # ValidationError
```

```python
@checked
def append(a: Sized[list[int], "m"], b: Sized[list[int], "n"]) -> Sized[list[int], "m + n"]:
    return a + b
```
