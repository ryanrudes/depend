from __future__ import annotations

from typing import Annotated

from depend import GreaterThan, Proof, RequiresProof, ValidationError, checked, ensured, prove, refined


PositiveInt = Annotated[int, GreaterThan[0]]
ProofForY = Annotated[Proof, RequiresProof["y", PositiveInt]]


@checked
def divide(x: float, y: PositiveInt, proof: ProofForY) -> float:
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
