from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

T = TypeVar("T")


@dataclass
class Registry:
    parent_by_child: dict[Any, Any] = field(default_factory=dict)
    children_by_parent: dict[Any, set[Any]] = field(default_factory=dict)
    label_by_item: dict[Any, str] = field(default_factory=dict)


REGISTRY = Registry()


def register(*, to: Any) -> Callable[[type[T]], type[T]]:
    def decorate(cls: type[T]) -> type[T]:
        parent_label = _ensure_label(to)
        children = _children_to_register(cls)
        for child in children:
            _register_child(child, parent=to, parent_label=parent_label)
        return cls

    return decorate


def parent_of(item: Any) -> Any | None:
    return REGISTRY.parent_by_child.get(item)


def children_of(parent: Any) -> tuple[Any, ...]:
    children = REGISTRY.children_by_parent.get(parent, set())
    return tuple(sorted(children, key=repr))


def label_of(item: Any) -> str:
    return _ensure_label(item)


def _register_child(child: Any, *, parent: Any, parent_label: str) -> None:
    existing_parent = REGISTRY.parent_by_child.get(child)
    if existing_parent is not None and existing_parent != parent:
        raise ValueError(f"{child!r} is already registered under {existing_parent!r}")

    REGISTRY.parent_by_child[child] = parent
    REGISTRY.children_by_parent.setdefault(parent, set()).add(child)
    REGISTRY.label_by_item[child] = f"{parent_label}:{_item_text(child)}"


def _ensure_label(item: Any) -> str:
    if item in REGISTRY.label_by_item:
        return REGISTRY.label_by_item[item]

    label = _item_text(item)
    REGISTRY.label_by_item[item] = label
    return label


def _item_text(item: Any) -> str:
    if isinstance(item, Enum):
        return str(item.value)
    return str(item)


def _children_to_register(cls: type[Any]) -> tuple[Any, ...]:
    children: list[Any] = []
    for name, value in vars(cls).items():
        if name.startswith("_"):
            continue
        if callable(value):
            continue
        children.append(value)
    return tuple(children)
