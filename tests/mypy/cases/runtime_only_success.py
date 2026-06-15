from typing import Annotated

from depend import checked, where

type RuntimeInt = Annotated[int, where(lambda x: x > 0, "must be positive")]


@checked
def f(x: RuntimeInt) -> None:
    pass


f(-1)
