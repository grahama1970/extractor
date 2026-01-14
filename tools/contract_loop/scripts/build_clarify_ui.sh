#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
UI_DIR="$PROJECT_ROOT/clarify-ui"

if [ ! -d "$UI_DIR" ]; then
  echo "Clarify UI directory not found at $UI_DIR" >&2
  exit 1
fi

echo "Installing dependencies..."
npm --prefix "$UI_DIR" install >/dev/null

echo "Building clarify UI..."
npm --prefix "$UI_DIR" run build

echo "Built assets at $UI_DIR/dist"
