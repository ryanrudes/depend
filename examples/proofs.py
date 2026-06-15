from __future__ import annotations

from depend import RequiresProof, ValidationError, checked, ensured, prove, refined


PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")


@checked
def divide(x: float, y: PositiveInt, proof: RequiresProof["y", PositiveInt]) -> float:
    return x / y


def main() -> None:
    y = 4
    proof = prove(y, PositiveInt)

    with ensured(y, PositiveInt) as value:
        print(divide(12.0, value, proof))

    try:
        divide(12.0, y, prove(y, refined(int, lambda x: x >= 0, name="NonNegativeInt")))
    except ValidationError as exc:
        print(exc)


if __name__ == "__main__":
    main()

