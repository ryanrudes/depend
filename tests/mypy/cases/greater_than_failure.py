from typing import Annotated

from depend import GreaterThan, checked

type PositiveInt = Annotated[int, GreaterThan[0]]


@checked
def f(x: PositiveInt) -> None:
    pass


f(-1)  # E: Argument 1 to f violates GreaterThan[0]: expected > 0, got Literal[-1]
