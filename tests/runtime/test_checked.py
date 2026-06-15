from __future__ import annotations

import asyncio

import pytest

from depend import ValidationError, checked, refined


PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")


def test_checked_validates_arguments_and_returns() -> None:
    @checked
    def identity(x: PositiveInt) -> PositiveInt:
        return x

    assert identity(3) == 3

    with pytest.raises(ValidationError):
        identity(-1)

    @checked
    def bad_return(x: PositiveInt) -> PositiveInt:
        return -x

    with pytest.raises(ValidationError):
        bad_return(1)


def test_checked_can_be_disabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPEND_DISABLE_CHECKS", "1")

    @checked
    def negating(x: PositiveInt) -> PositiveInt:
        return -x

    assert negating(-1) == 1


def test_checked_async_support() -> None:
    @checked
    async def identity(x: PositiveInt) -> PositiveInt:
        return x

    assert asyncio.run(identity(2)) == 2

    with pytest.raises(ValidationError):
        asyncio.run(identity(0))
