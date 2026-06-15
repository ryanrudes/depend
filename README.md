# depend

[![CI](https://github.com/ryanrudes/depend/actions/workflows/ci.yml/badge.svg)](https://github.com/ryanrudes/depend/actions/workflows/ci.yml)
[![Docs](https://github.com/ryanrudes/depend/actions/workflows/pages.yml/badge.svg)](https://github.com/ryanrudes/depend/actions/workflows/pages.yml)
[![GitHub Pages](https://img.shields.io/badge/docs-GitHub%20Pages-2a6fbb)](https://ryanrudes.github.io/depend/)

`depend` provides dependent-style typing for Python: runtime-validated, statically assisted, and built around structured predicates.

It is designed for ordinary Python code that needs more shape than `Any` but should still run normally without a custom checker.

## Highlights

- refinements with `Predicate` and `where`
- `@checked` runtime validation for arguments and returns
- `Sized` symbolic lengths
- NumPy shape and dtype annotations
- proof objects for validated values
- registry metadata for structured hierarchies
- an optional mypy plugin for structured predicates

## Docs

- Live site: [https://ryanrudes.github.io/depend/](https://ryanrudes.github.io/depend/)
- Build the site with `uv run mkdocs build`
- Serve it locally with `uv run mkdocs serve`
- Read the topic pages in `docs/`

## Repository setup

- Install the repo hooks with `bash scripts/install-git-hooks.sh`
- Run the validation bundle with `agents/hooks/preflight.sh`, `uv run pytest -q`, `uv run mypy .`, and `uv run python -m compileall -q src tests`
- Use `docs/` as the MkDocs source and `site/` as the generated output

## Examples

Runnable examples live in `examples/`.
