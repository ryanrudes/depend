# Workflow: New Feature

1. Read `agents/AGENTS.md`.
2. Identify whether the feature is runtime, static plugin, or docs.
3. Implement runtime behavior first.
4. Add tests before broad refactors.
5. Add mypy plugin support only after runtime behavior is stable.
6. Update docs if public API changes.
7. Run relevant validation.
8. Summarize what changed and what was not proven statically.

## Feature rule

Every static feature must degrade to runtime validation when the plugin cannot prove it.
