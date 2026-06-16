from __future__ import annotations

from typing import Annotated

from depend import Context, Sized, ValidationError, checked, validate


SizedIntList = Annotated[list[int], Sized[list[int], "n"]]


def main() -> None:
    annotation = SizedIntList
    ctx = Context(path=("values",))

    print(validate([1, 2, 3], annotation, ctx))
    print(ctx.symbols["n"])

    @checked
    def dot(a: SizedIntList, b: SizedIntList) -> int:
        return sum(a) + sum(b)

    print(dot([1, 2], [3, 4]))

    try:
        dot([1, 2], [3])
    except ValidationError as exc:
        print(exc)


if __name__ == "__main__":
    main()
