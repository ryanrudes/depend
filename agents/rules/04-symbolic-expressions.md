# Rule: Symbolic Expressions

Symbolic expressions power `Sized` and `Shape` constraints.

## Allowed expression forms

Support only a restricted arithmetic subset:

```text
n
m
n + m
n - 1
n * 2
2 * n
```

Allowed AST nodes:

- `ast.Name`
- integer `ast.Constant`
- `ast.BinOp` with `Add`, `Sub`, `Mult`

Reject everything else:

- function calls
- attribute access
- indexing
- comprehensions
- lambdas
- imports
- arbitrary expressions

## Why

Symbolic dimensions need to be safe, inspectable, serializable, and plugin-readable. Letting users write arbitrary Python in type parameters is how a shape checker becomes a second interpreter with worse error messages.
