# Rule: mypy Plugin Architecture

The mypy plugin provides static assistance for structured, decidable constraints.

## Plugin responsibilities

The plugin may:

- recognize known predicates such as `GreaterThan[0]`, `Between[0, 1]`, `NonEmpty`, `StrictlyIncreasing`
- narrow after `ensure(value, Annotation)`
- reject obvious literal violations
- track simple `Sized[..., "n"]` constraints
- track simple `NDArray[Shape[...], DType[...]]` constraints
- assist value-indexed APIs when static metadata or generated overloads are available

## Plugin non-responsibilities

The plugin must not:

- execute arbitrary user predicates
- import and run user modules for proof
- attempt full arbitrary Python theorem proving
- block code that must be deferred to runtime validation

For arbitrary predicates, emit clear notes only when useful:

```text
Runtime-only predicate cannot be proven statically. Use a known structured predicate or ensure(...).
```

## Design rule

Known structured predicates are statically assisted. Arbitrary lambdas are runtime-only.

This split is not weakness; it is civilization.
