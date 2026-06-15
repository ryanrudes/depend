from typing import Annotated

from depend import Between, checked

type SmallInt = Annotated[int, Between[0, 10]]


@checked
def f(x: SmallInt) -> None:
    pass


f(15)  # E: Argument 1 to f violates Between[0, 10]: expected between 0 and 10, got Literal[15]
