# Rule: Project Scope

This repository is for `depend`, a Python runtime validation library plus mypy plugin for gradual dependent-style typing.

## Primary goals

- Provide idiomatic runtime validation through normal Python annotations.
- Use `typing.Annotated` for refinements.
- Support structured, plugin-readable predicates.
- Support symbolic dimensions and sizes.
- Support shape-safe NumPy annotations.
- Support proof objects for previously validated values.
- Support `@checked` functions and checked dataclasses.
- Provide a mypy plugin for static assistance.

## Non-goals

- Full static proof of arbitrary Python predicates.
- Replacing mypy with a complete new checker in v1.
- A custom Python dialect.
- Runtime monkeypatching.
- AST rewriting of user code.
- Making users write proof terms for ordinary validation.

## Honesty requirement

When documenting the project, describe it as:

> dependent-style typing for Python: runtime-validated, statically assisted

Do not describe it as:

> full dependent types in Python

unless the project later ships a real standalone checker with a sound restricted language. Which, sure, maybe after we all get extra lifetimes.
