# Rule: Documentation

Docs must be honest, practical, and example-driven.

## Required docs topics

- refinements
- known predicates versus runtime-only predicates
- `@checked`
- `Sized`
- NumPy shapes
- proof objects
- dataclass validation
- registry metadata
- mypy plugin setup
- limitations

## Wording rules

Use:

```text
dependent-style typing
runtime-validated
statically assisted
structured predicates
```

Avoid overclaiming:

```text
full dependent types in Python
sound theorem proving over arbitrary Python
```

Unless the project actually ships a standalone restricted checker, do not pretend the mypy plugin can solve arbitrary Python truth. The halting problem has enough publicity already.
