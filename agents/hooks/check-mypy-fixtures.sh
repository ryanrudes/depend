#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d tests/mypy ]]; then
  echo 'mypy fixture check: tests/mypy does not exist yet'
  exit 0
fi

uv run pytest tests/mypy -q
