# Codex Agents Folder for depend

This folder contains project-specific instructions for Codex agents working on the `depend` Python library and mypy plugin.

Start with:

```text
agents/AGENTS.md
```

Then consult:

- `agents/rules/` for standing rules
- `agents/commands/` for task-specific instructions
- `agents/context/` for design context
- `agents/workflows/` for process guidance
- `agents/hooks/` for validation scripts
- `agents/templates/` for PR/handoff summaries

This agents folder is intentionally generic to the `depend` project. It should not mention retargeting-specific architecture except as examples in future docs, because apparently context leakage is how the machines embarrass themselves.
