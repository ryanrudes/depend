#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f pyproject.toml ]]; then
  echo "preflight: pyproject.toml not found"
  exit 1
fi

if ! grep -Eq 'requires-python[[:space:]]*=[[:space:]]*">=3\.12"' pyproject.toml; then
  echo 'preflight: pyproject.toml must set requires-python = ">=3.12"'
  exit 1
fi

if ! grep -Eq 'build-backend[[:space:]]*=[[:space:]]*"hatchling\.build"' pyproject.toml; then
  echo 'preflight: pyproject.toml must use build-backend = "hatchling.build"'
  exit 1
fi

if grep -Eq '\[tool\.(poetry|pdm|flit)\]' pyproject.toml; then
  echo 'preflight: do not introduce Poetry, PDM, or Flit configuration'
  exit 1
fi

if [[ -d src || -d tests ]]; then
  if grep -R "from typing import TypeVar\|typing.TypeVar" src tests --include='*.py' 2>/dev/null; then
    echo 'preflight warning: TypeVar found. Prefer PEP 695 syntax unless mypy/plugin limitations require TypeVar.'
  fi
fi

echo 'preflight: ok'
