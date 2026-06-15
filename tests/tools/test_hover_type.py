from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "hover_type.py"


def run_hover(file_path: Path, line: int, column: int) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(file_path), "--line", str(line), "--column", str(column)],
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


def test_hover_reports_alias_parameter_and_ensure_binding(tmp_path: Path) -> None:
    source = textwrap.dedent(
        """
        from typing import Annotated
        from depend import GreaterThan, checked, ensure

        type PositiveInt = Annotated[int, GreaterThan[0]]

        @checked
        def f(x: PositiveInt) -> PositiveInt:
            return x

        y = ensure(3, PositiveInt)
        print(y)
        """
    ).lstrip("\n")
    file_path = tmp_path / "sample.py"
    file_path.write_text(source, encoding="utf-8")

    alias = run_hover(file_path, 4, 6)
    assert alias["symbol"] == "PositiveInt"
    assert alias["computed_type"] == "Annotated[int, GreaterThan[0]]"
    assert alias["kind"] == "type_alias"

    parameter = run_hover(file_path, 7, 7)
    assert parameter["symbol"] == "x"
    assert parameter["computed_type"] == "PositiveInt"
    assert parameter["kind"] == "parameter"

    ensured = run_hover(file_path, 11, 7)
    assert ensured["symbol"] == "y"
    assert ensured["computed_type"] == "PositiveInt"
    assert ensured["kind"] == "ensure"
