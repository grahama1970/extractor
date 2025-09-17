#!/usr/bin/env bash
set -euo pipefail

# Simple, one-shot CLI validator runner.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

test -d .venv && source .venv/bin/activate || true
set -a && [ -f .env ] && source .env && set +a || true

PY="${PYTHON:-python}"
TASKS_FILE="${TASKS:-data/cli_tasks.json}"
CWD="${CWD:-$ROOT_DIR}"

"$PY" scripts/validate_cli.py run --tasks-file "$TASKS_FILE" --cwd "$CWD"

