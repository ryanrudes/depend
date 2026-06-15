from __future__ import annotations

from depend import Context, Sized, ValidationError, checked, validate


def main() -> None:
    annotation = Sized[list[int], "n"]
    ctx = Context(path=("values",))

    print(validate([1, 2, 3], annotation, ctx))
    print(ctx.symbols["n"])

    @checked
    def dot(a: Sized[list[int], "n"], b: Sized[list[int], "n"]) -> int:
        return sum(a) + sum(b)

    print(dot([1, 2], [3, 4]))

    try:
        dot([1, 2], [3])
    except ValidationError as exc:
        print(exc)


if __name__ == "__main__":
    main()

