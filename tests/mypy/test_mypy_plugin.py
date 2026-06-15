from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "tests" / "mypy.ini"
CASES = ROOT / "tests" / "mypy" / "cases"


@pytest.mark.parametrize(
    ("case_name", "should_pass", "expected"),
    [
        ("ensure_narrowing_success.py", True, "Success: no issues found"),
        ("runtime_only_success.py", True, "Success: no issues found"),
        ("greater_than_failure.py", False, "violates GreaterThan[0]"),
        ("between_failure.py", False, "violates Between[0, 10]"),
    ],
)
def test_mypy_plugin(case_name: str, should_pass: bool, expected: str) -> None:
    case = CASES / case_name
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--config-file", str(CONFIG), str(case)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )

    output = result.stdout
    if should_pass:
        assert result.returncode == 0, output
        assert expected in output, output
    else:
        assert result.returncode != 0, output
        assert expected in output, output
