#!/usr/bin/env bash
set -euo pipefail

# Simple, one-shot API validator runner.
# Starts uvicorn on PORT (default 8000), waits, runs validator, and exits.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

test -d .venv && source .venv/bin/activate || true
set -a && [ -f .env ] && source .env && set +a || true

PY="${PYTHON:-python}"
PORT="${PORT:-8000}"
TARGET="${TARGET:-http://127.0.0.1:${PORT}}"
TASKS_FILE="${TASKS:-data/api_tasks.json}"

"$PY" -m uvicorn extractor.core.scripts.server:app --host 127.0.0.1 --port "$PORT" &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT INT TERM

# Wait until server responds
OK=0
for i in {1..120}; do
  if curl -sf "${TARGET}/" >/dev/null; then OK=1; break; fi
  sleep 0.5
done
if [ "$OK" -ne 1 ]; then
  echo "timeout: server on $PORT not ready" >&2
  exit 1
fi

"$PY" scripts/validate_api.py run --target "$TARGET" --api-base "$TARGET" --tasks-file "$TASKS_FILE"

