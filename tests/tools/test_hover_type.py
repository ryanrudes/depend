from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "hover_type.py"
MYPY_CONFIG = ROOT / "tests" / "mypy.ini"


def run_hover(
    file_path: Path,
    line: int,
    column: int,
    *,
    include_base: bool = False,
    mypy_config: Path | None = MYPY_CONFIG,
) -> dict[str, object]:
    args = [
        sys.executable,
        str(SCRIPT),
        "--file",
        str(file_path),
        "--line",
        str(line),
        "--column",
        str(column),
    ]
    if mypy_config is not None:
        args.extend(["--mypy-config", str(mypy_config)])
    if include_base:
        args.append("--include-base")
    result = subprocess.run(
        args,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    return payload


def test_hover_reports_computed_and_refined_types(tmp_path: Path) -> None:
    source = textwrap.dedent(
        """
        from enum import Enum
        from typing import Annotated
        from depend import GreaterThan, checked, ensure, parent_of, label_of, register

        type PositiveInt = Annotated[int, GreaterThan[0]]

        class Topics(Enum):
            RUNTIME = "runtime"

        @register(to=Topics.RUNTIME)
        class RuntimeFragments:
            VALIDATE = "validate"

        @checked
        def f(x: PositiveInt) -> PositiveInt:
            print(x)

        x = parent_of(RuntimeFragments.VALIDATE)
        y = ensure(3, PositiveInt)
        print(x)
        print(y)
        print(RuntimeFragments.VALIDATE)
        print(label_of(RuntimeFragments.VALIDATE))
        """
    ).lstrip("\n")
    file_path = tmp_path / "sample.py"
    file_path.write_text(source, encoding="utf-8")

    alias = run_hover(file_path, 5, 6, include_base=True)
    assert alias["symbol"] == "PositiveInt"
    assert alias["computed_type"] == "Annotated[int, GreaterThan[0]]"
    assert alias["kind"] == "type_alias"
    assert alias["base_type"] == "typing.TypeAliasType"

    parameter = run_hover(file_path, 16, 11, include_base=True)
    assert parameter["symbol"] == "x"
    assert parameter["computed_type"] == "int"
    assert parameter["kind"] == "mypy"
    assert parameter["base_type"] == "PositiveInt"

    parent = run_hover(file_path, 18, 1, include_base=True)
    assert parent["symbol"] == "x"
    assert parent["computed_type"] == "Literal[sample.Topics.RUNTIME]"
    assert parent["kind"] == "mypy"
    assert parent["base_type"] == "parent_of(RuntimeFragments.VALIDATE)"

    ensured = run_hover(file_path, 19, 1, include_base=True)
    assert ensured["symbol"] == "y"
    assert ensured["computed_type"] == "int"
    assert ensured["kind"] == "mypy"
    assert ensured["base_type"] == "PositiveInt"

    member = run_hover(file_path, 22, 17, include_base=True)
    assert member["symbol"] == "RuntimeFragments.VALIDATE"
    assert member["computed_type"] == "Literal['validate']?"
    assert member["kind"] == "mypy"

    label = run_hover(file_path, 23, 7, include_base=True)
    assert label["symbol"] == "label_of"
    assert label["computed_type"] == "Literal['runtime:validate']"
    assert label["kind"] == "mypy"


def test_hover_tracks_control_flow_narrowing(tmp_path: Path) -> None:
    source = textwrap.dedent(
        """
        def g(value: int | str) -> None:
            if isinstance(value, int):
                narrowed = value
                print(narrowed)
        """
    ).lstrip("\n")
    file_path = tmp_path / "flow.py"
    file_path.write_text(source, encoding="utf-8")

    narrowed = run_hover(file_path, 3, 9, include_base=True)
    assert narrowed["symbol"] == "narrowed"
    assert narrowed["computed_type"] == "int"
    assert narrowed["kind"] == "mypy"
    assert narrowed["base_type"] == "value"
