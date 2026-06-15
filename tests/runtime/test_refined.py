from __future__ import annotations

from typing import Annotated, get_args, get_origin

import pytest

from depend import Between, Finite, GreaterThan, NonEmpty, ValidationError, ensure, is_valid, refined, validate


def test_refined_builds_annotated_alias() -> None:
    PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")

    assert get_origin(PositiveInt) is Annotated
    base, predicate = get_args(PositiveInt)
    assert base is int
    assert predicate.name == "PositiveInt"


def test_validate_accepts_and_rejects_refinements() -> None:
    PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")

    assert validate(3, PositiveInt) == 3
    with pytest.raises(ValidationError) as excinfo:
        validate(-1, PositiveInt)
    assert "PositiveInt" in str(excinfo.value)
    assert "got -1" in str(excinfo.value)


def test_known_predicates_work() -> None:
    assert validate(3, GreaterThan[0]) == 3
    assert validate(0.5, Between[0.0, 1.0]) == 0.5
    assert validate([1, 2], NonEmpty) == [1, 2]
    assert validate(3.5, Finite) == 3.5

    with pytest.raises(ValidationError):
        validate(0, GreaterThan[0])


def test_ensure_and_is_valid() -> None:
    PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")

    assert ensure(5, PositiveInt) == 5
    assert is_valid(5, PositiveInt) is True
    assert is_valid(-5, PositiveInt) is False
