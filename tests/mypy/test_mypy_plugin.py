from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "tests" / "mypy.ini"
CASES = ROOT / "tests" / "mypy" / "cases"
EXAMPLES = ROOT / "examples"


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


def test_registry_and_validate_types() -> None:
    case = CASES / "registry_and_validate_success.py"
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--config-file", str(CONFIG), str(case)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )

    output = result.stdout
    assert result.returncode == 0, output
    assert (
        output.count('Revealed type is "Literal[4]?"') == 2
        or output.count('Revealed type is "int"') == 2
    ), output
    assert 'Revealed type is "Literal[\'validate\']?"' in output, output
    assert (
        'Revealed type is "Literal[\'runtime\']?"' in output
        or 'Revealed type is "Literal[registry_and_validate_success.Topics.RUNTIME]"' in output
    ), output
    assert 'Revealed type is "Literal[\'runtime:validate\']"' in output, output
    assert 'Revealed type is "tuple[' in output and "validate" in output, output


def test_validate_and_ensure_failures() -> None:
    source = textwrap.dedent(
        """
        from typing import Annotated

        from depend import GreaterThan, ensure, validate

        type PositiveInt = Annotated[int, GreaterThan[0]]

        validate(-1, PositiveInt)
        ensure(-1, PositiveInt)
        """
    ).lstrip("\n")

    with tempfile.TemporaryDirectory() as tmp:
        case = Path(tmp) / "validate_failure.py"
        case.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--config-file", str(CONFIG), str(case)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )

    output = result.stdout
    assert result.returncode != 0, output
    assert "Argument 1 to validate violates GreaterThan[0]" in output, output
    assert "Argument 1 to ensure violates GreaterThan[0]" in output, output


@pytest.mark.parametrize(
    ("example_name", "should_pass", "expected"),
    [
        ("proofs.py", True, "Success: no issues found"),
        ("sized_collections.py", True, "Success: no issues found"),
        ("numpy_shapes.py", True, "Success: no issues found"),
        ("refinements.py", True, "Success: no issues found"),
        ("registries.py", True, "Success: no issues found"),
        ("checked_functions.py", False, "Argument 2 to repeat violates GreaterThan[0]"),
    ],
)
def test_examples_mypy(example_name: str, should_pass: bool, expected: str) -> None:
    example = EXAMPLES / example_name
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--config-file", str(CONFIG), str(example)],
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
