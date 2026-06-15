from __future__ import annotations

from enum import Enum

from depend import children_of, label_of, parent_of, register


class Topics(Enum):
    RUNTIME = "runtime"
    STATIC = "static"


@register(to=Topics.RUNTIME)
class RuntimeFragments:
    VALIDATE = "validate"
    CHECKED = "checked"


def main() -> None:
    print(label_of(Topics.RUNTIME))
    print(label_of(RuntimeFragments.VALIDATE))
    print(parent_of(RuntimeFragments.VALIDATE))
    print(children_of(Topics.RUNTIME))


if __name__ == "__main__":
    main()

