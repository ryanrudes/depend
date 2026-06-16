from __future__ import annotations

from typing import Annotated

from depend import GreaterThan, ValidationError, checked, ensure

PositiveInt = Annotated[int, GreaterThan[0]]


@checked
def repeat(text: str, n: PositiveInt) -> str:
    return text * n


@checked
def broken(n: PositiveInt) -> PositiveInt:
    return -n


def main() -> None:
    print(repeat("ha", ensure(3, PositiveInt)))

    try:
        repeat("ha", -1)
    except ValidationError as exc:
        print(exc)

    try:
        broken(1)
    except ValidationError as exc:
        print(exc)


if __name__ == "__main__":
    main()
