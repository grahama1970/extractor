#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
UI_DIR="$PROJECT_ROOT/clarify-ui"
PORT=${PORT:-4173}
API_BASE=${VITE_API_BASE:-http://127.0.0.1:5057}

if [ ! -d "$UI_DIR" ]; then
  echo "Clarify UI directory not found at $UI_DIR" >&2
  exit 1
fi

echo "Starting clarify UI dev server on port $PORT (API: $API_BASE)..."
VITE_API_BASE="$API_BASE" npm --prefix "$UI_DIR" run dev -- --host 127.0.0.1 --port "$PORT"
