from enum import Enum
from typing import Annotated

from depend import GreaterThan, children_of, ensure, label_of, parent_of, register, validate

type PositiveInt = Annotated[int, GreaterThan[0]]


class Topics(Enum):
    RUNTIME = "runtime"


@register(to=Topics.RUNTIME)
class RuntimeFragments:
    VALIDATE = "validate"


reveal_type(validate(4, PositiveInt))
reveal_type(ensure(4, PositiveInt))
reveal_type(RuntimeFragments.VALIDATE)
reveal_type(parent_of(RuntimeFragments.VALIDATE))
reveal_type(label_of(RuntimeFragments.VALIDATE))
reveal_type(children_of(Topics.RUNTIME))
