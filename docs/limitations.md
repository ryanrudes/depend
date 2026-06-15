# Limitations

`depend` is dependent-style typing, not full dependent types in Python.

The important edges are:

- runtime-only predicates such as `where(lambda x: expensive(x))` are not statically provable
- the mypy plugin only understands structured predicate metadata in `Annotated[...]`
- `Sized` and NumPy shape checks are runtime-validated, and static coverage is limited
- proof objects are runtime certificates, not theorem prover artifacts
- validation still depends on the actual values and the current runtime context

That is deliberate. The project is meant to be runtime-validated and statically assisted, not a promise that arbitrary Python can be turned into math.

