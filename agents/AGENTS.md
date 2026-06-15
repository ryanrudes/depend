# AGENTS.md

Guidance for Codex agents working on the `depend` Python library and mypy plugin.

## Mission

Build `depend`: a human-friendly, idiomatic Python library for gradual dependent-style typing with runtime validation and mypy-assisted static proof for structured constraints.

The project should make dependent-style programming feel like normal Python:

- use ordinary Python annotations;
- prefer `typing.Annotated` for refinements;
- validate at runtime explicitly via `@checked`, `validate`, and `ensure`;
- statically assist with a mypy plugin where proof is tractable;
- degrade honestly to runtime validation where proof is unavailable.

Do not turn Python into a fake Idris cosplay event. The type system is already dramatic enough.

## Packaging and typing invariants

This project is packaged with `uv` and uses Hatch / `hatchling` as the build backend. It supports Python 3.12+ only.

Use modern Python typing throughout. Prefer PEP 695 syntax for generic classes, generic functions, and type aliases. Avoid legacy `TypeVar`-heavy patterns unless a current type checker or library limitation requires them.

Do not introduce alternate packaging systems such as Poetry, Pipenv, setuptools-only configuration, PDM, Flit, or conda environment assumptions.

## Core architecture

The project has four conceptual layers:

1. Runtime validation library
   - `Predicate`
   - `where`
   - `refined`
   - `validate`
   - `ensure`
   - `@checked`
   - `Sized`
   - `NDArray`
   - dataclass validation
   - proofs
   - registry metadata

2. Static metadata
   - structured predicate metadata
   - symbolic expressions
   - shape/dimension specs
   - constraint specs
   - registry specs

3. mypy plugin
   - narrows `ensure(...)`
   - recognizes known predicates
   - checks obvious literal failures
   - tracks simple symbolic dimensions
   - assists with `Sized` and `NDArray`

4. Optional codegen/stubs
   - generates `Literal` overloads for value-indexed APIs when static metadata must be explicit.

Runtime behavior must always work without the plugin. Static support is additive.

## Implementation order

Follow this order unless the user explicitly says otherwise:

1. Runtime refinements
2. `@checked`
3. symbolic expressions and `Sized`
4. dataclasses and proofs
5. NumPy shape support
6. registry metadata
7. mypy plugin MVP
8. mypy `Sized` support
9. mypy `NDArray` support
10. docs and examples

Every feature must work at runtime before static support is added.

## What not to do

- Do not try to prove arbitrary Python lambdas statically in v1.
- Do not execute user predicates inside mypy.
- Do not use import hooks, AST rewriting, monkeypatching, or global function interception.
- Do not wrap normal Python values unless the user explicitly asks for proof objects or wrappers.
- Do not claim full dependent typing soundness for arbitrary Python.
- Do not allow arbitrary Python expressions in symbolic dimensions.

The plugin should be an incomplete but useful prover over structured metadata, not a tiny theorem goblin living inside mypy.

## Validation rule

Before finishing a code task, run the relevant subset of:

```bash
uv run pytest -q
uv run mypy .
uv run python -m compileall -q src tests
agents/hooks/preflight.sh
```

If a command is unavailable or fails for environment reasons, report exactly what happened.
