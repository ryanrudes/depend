from typing import Annotated

from depend import GreaterThan, checked, ensure

type PositiveInt = Annotated[int, GreaterThan[0]]


@checked
def f(x: PositiveInt) -> None:
    pass


def get_int() -> int:
    return -1


f(ensure(get_int(), PositiveInt))
