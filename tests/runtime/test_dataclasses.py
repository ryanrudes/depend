from __future__ import annotations

from dataclasses import dataclass

import pytest

from depend import ValidationError, checked_dataclass, dependent_dataclass, refined


PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")


def test_checked_dataclass_validates_after_post_init_by_default() -> None:
    events: list[str] = []

    @checked_dataclass
    @dataclass
    class Config:
        port: PositiveInt

        def __post_init__(self) -> None:
            events.append("post_init")
            self.port = int(self.port)

    config = Config("7")
    assert config.port == 7
    assert events == ["post_init"]


def test_checked_dataclass_can_validate_before_post_init() -> None:
    @checked_dataclass(validate_before_post_init=True)
    @dataclass
    class Config:
        port: PositiveInt

        def __post_init__(self) -> None:
            self.port = int(self.port)

    with pytest.raises(ValidationError):
        Config("7")


def test_dependent_dataclass_convenience_decorator() -> None:
    @dependent_dataclass
    class Settings:
        port: PositiveInt

    settings = Settings(11)
    assert settings.port == 11

    with pytest.raises(ValidationError):
        Settings(-1)
