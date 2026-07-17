#!/bin/bash
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# Install the project + dev tooling (pytest, mypy, pre-commit) into the uv-managed venv.
uv sync

# Installs the git hook (so `git commit` runs it automatically) and
# pre-warms hook environments/cache. Pre-existing findings shouldn't block
# session start, so this step is non-blocking - failures surface as normal
# output for the agent to see and address, not a broken session.
uv run pre-commit install
uv run pre-commit run --all-files || true
