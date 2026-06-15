# Workflow: mypy Plugin Feature

1. Define the structured metadata the plugin will understand.
2. Add runtime behavior first.
3. Add mypy fixture success and failure cases.
4. Implement plugin hook.
5. Ensure arbitrary runtime predicates still degrade gracefully.
6. Document static limitations.

## Never

Never execute arbitrary user code inside mypy. That way lies sadness, nondeterminism, and probably someone opening a socket from a type annotation.
