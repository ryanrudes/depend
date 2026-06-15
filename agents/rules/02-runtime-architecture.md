# Rule: Runtime Architecture

Runtime validation is the foundation. Every dependent-style feature must work at runtime before static support is added.

## Core runtime objects

Implement and maintain clear boundaries between:

- `Predicate`: runtime predicate plus optional static metadata
- `Context`: validation state, values, symbols, proof bindings, error paths
- `Expr`: restricted symbolic arithmetic expression
- `SizedAnnotation`: collection plus length expression
- `ShapeAnnotation`: array shape dimensions
- `DTypeAnnotation`: NumPy dtype constraint
- `Proof`: runtime certificate that a value satisfied an annotation

## Runtime validation principles

- Return original values on success.
- Raise structured `ValidationError` on failure.
- Avoid wrapping values by default.
- Preserve normal Python object behavior.
- Keep validation explicit through `validate`, `ensure`, `@checked`, or checked dataclass decorators.

## Error messages

Errors must include:

- location: function argument, return value, dataclass field, or nested path
- expected constraint
- actual value summary
- symbol bindings when relevant
- helpful predicate name or message

Good:

```text
ValidationError in dot argument b:
  expected len(b) == n
  where n = 3 from argument a
  got len(b) = 2
```

Bad:

```text
predicate failed
```

Bad errors are how good libraries become interrogation devices.
