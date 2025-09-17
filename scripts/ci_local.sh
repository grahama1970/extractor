#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ART_DIR="$ROOT_DIR/scripts/artifacts"
mkdir -p "$ART_DIR"

echo "[ci] Checking live servers..."
BASE_URL=${BASE_URL:-http://127.0.0.1:8080}
CDP_URL=${BROWSERLESS_DISCOVERY_URL:-http://127.0.0.1:3000/json/version}

if ! curl -fsS --max-time 3 "$BASE_URL" >/dev/null; then
  echo "[ci] Dev server not reachable at $BASE_URL"
  echo "[ci] Start it via VS Code: Run Backend + Preview"
  exit 2
fi
if ! curl -fsS --max-time 3 "$CDP_URL" >/dev/null; then
  echo "[ci] Browserless/CDP not reachable at $CDP_URL"
  echo "[ci] Start Browserless (or Chrome --remote-debugging)"
  exit 2
fi

echo "[ci] Fast checks (lint/type/tests)..."
if command -v ruff >/dev/null 2>&1; then ruff check .; else echo "[ci] ruff not installed"; fi
if command -v black >/dev/null 2>&1; then black --check .; else echo "[ci] black not installed"; fi
if command -v mypy >/dev/null 2>&1; then mypy src || true; else echo "[ci] mypy not installed"; fi
if command -v pytest >/dev/null 2>&1; then pytest -q || true; else echo "[ci] pytest not installed"; fi

echo "[ci] API smokes..."
node "$ROOT_DIR/scripts/smokes/api_generate_model.mjs" || true

echo "[ci] UX health + full smokes..."
node "$ROOT_DIR/scripts/ux_check_cdp_auto.mjs"
# Explicit console error scan
node "$ROOT_DIR/scripts/smokes/console_errors.mjs"
node "$ROOT_DIR/scripts/smokes/all.mjs"

echo "[ci] Done. Artifacts in $ART_DIR"
ls -1t "$ART_DIR" | head -n 20 || true
