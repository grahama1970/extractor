#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MARKER_DIR="$ROOT_DIR/repos/marker"

if [[ ! -d "$MARKER_DIR" ]]; then
  echo "Error: repos/marker not found. Clone your Marker fork into repos/marker." >&2
  exit 1
fi

if [[ -d "$ROOT_DIR/.venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
else
  command -v uv >/dev/null 2>&1 || { echo "uv not found; please create a venv and install deps"; exit 2; }
  uv venv
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
fi

set -x
uv pip install -e "$MARKER_DIR"[dev] || { uv pip install -e "$MARKER_DIR" && uv pip install pytest; }
cd "$MARKER_DIR"
pytest -q
