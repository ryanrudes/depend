# mypy Plugin Scope

## Supported in v1

- known predicate metadata
- literal checks for simple predicates
- `ensure(...)` narrowing
- basic `Sized` metadata
- basic `NDArray` shape metadata

## Deferred

- arbitrary lambda proof
- complex control-flow theorem proving
- Pyright plugin
- standalone checker
- narrowing inside custom context managers
- generated overload tooling

## Static support categories

### Static + runtime

Structured predicates:

```python
GreaterThan[0]
Between[0, 1]
NonEmpty
Sized[list[int], "n"]
NDArray[Shape["T", 3], Float64]
```

### Runtime only

Arbitrary predicates:

```python
where(lambda x: expensive_check(x))
```

### Static via generated stubs

Value-indexed APIs:

```python
@overload
def subject(self, subject: Literal[Subject.LEFT]) -> LeftSubject: ...
```
