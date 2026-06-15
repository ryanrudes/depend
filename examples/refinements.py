from __future__ import annotations

from typing import Annotated

from depend import Between, GreaterThan, ValidationError, refined, validate, where


PositiveInt = Annotated[int, GreaterThan[0]]
OddInt = refined(int, lambda x: x % 2 == 1, name="OddInt")
Probability = Annotated[float, Between[0.0, 1.0]]
EvenInt = Annotated[int, where(lambda x: x % 2 == 0, "must be even")]


def main() -> None:
    print(validate(3, PositiveInt))
    print(validate(0.25, Probability))
    print(validate(5, OddInt))

    try:
        validate(3, EvenInt)
    except ValidationError as exc:
        print(exc)


if __name__ == "__main__":
    main()

