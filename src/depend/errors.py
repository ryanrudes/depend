from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


def summarize_value(value: Any, *, limit: int = 80) -> str:
    if isinstance(value, str):
        if len(value) <= limit:
            return repr(value)
        return repr(value[: max(0, limit - 5)])[:-1] + "...'"

    if isinstance(value, (list, tuple, set, frozenset, dict)):
        preview = repr(value)
        if len(preview) <= limit:
            return preview
        return preview[: max(0, limit - 3)] + "..."

    preview = repr(value)
    if len(preview) <= limit:
        return preview
    return preview[: max(0, limit - 3)] + "..."


def format_path(path: tuple[str, ...]) -> str:
    if not path:
        return ""
    return " in " + " ".join(path)


@dataclass(slots=True)
class ValidationError(TypeError):
    path: tuple[str, ...]
    expected: str
    actual: str
    details: str | None = None
    context: Mapping[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        lines = [f"ValidationError{format_path(self.path)}:", f"  expected {self.expected}"]
        if self.details:
            for line in self.details.splitlines():
                lines.append(f"  {line}")
        lines.append(f"  got {self.actual}")
        return "\n".join(lines)
