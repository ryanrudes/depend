from __future__ import annotations

import pytest

from depend import Context, Sized, ValidationError, checked, validate


def test_sized_direct_validation_binds_symbols() -> None:
    annotation = Sized[list[int], "n"]
    ctx = Context(path=("values",))

    assert validate([1, 2, 3], annotation, ctx) == [1, 2, 3]
    assert ctx.symbols["n"] == 3
    assert ctx.symbol_sources["n"] == "values"


def test_sized_rejects_length_mismatch() -> None:
    annotation = Sized[list[int], "n + 1"]
    ctx = Context(path=("values",))
    ctx.bind_symbol("n", 2, source="prior binding")

    with pytest.raises(ValidationError) as excinfo:
        validate([1, 2], annotation, ctx)

    assert "len(values) == n + 1" in str(excinfo.value)


def test_checked_reuses_symbol_bindings_across_arguments() -> None:
    @checked
    def dot(a: Sized[list[int], "n"], b: Sized[list[int], "n"]) -> int:
        return sum(a) + sum(b)

    assert dot([1, 2], [3, 4]) == 10

    with pytest.raises(ValidationError):
        dot([1, 2], [3])
