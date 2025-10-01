#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

find_free_port() {
  local start="${1:-8000}"; local tries=50; local p=$start
  for i in $(seq 0 $tries); do
    if ! ss -ltn 2>/dev/null | grep -Eq ":${p}\\b"; then echo "$p"; return 0; fi
    p=$((p+1))
  done
  return 1
}

wait_for_listen() {
  local PORT="$1"; local TRIES="${2:-40}"; local DELAY="${3:-0.25}"; local i=0
  while [ "$i" -lt "$TRIES" ]; do
    if ss -ltn 2>/dev/null | grep -Eq ":${PORT}\\b"; then return 0; fi
    sleep "$DELAY" || true; i=$((i+1))
  done
  return 1
}

detect_vite_port() {
  local START="$1"; local MAX_DELTA="${2:-30}"; local TRIES="${3:-60}"; local DELAY="${4:-0.25}"
  local j=0
  while [ "$j" -lt "$TRIES" ]; do
    for p in $(seq "$START" $((START+MAX_DELTA))); do
      if ss -ltnp 2>/dev/null | awk -v pr=":$p" '$0~pr && $0~/(node|vite)/ {print}' | grep -q ":$p"; then
        echo "$p"; return 0
      fi
    done
    sleep "$DELAY" || true; j=$((j+1))
  done
  return 1
}

ensure_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Missing $1" >&2; exit 1; }; }

ensure_cmd node || true
ensure_cmd npm || true

PY="${VENV_PY:-${PWD}/.venv/bin/python}"
if [ ! -x "$PY" ]; then PY="python"; fi
BACK_PID=""; VITE_PID=""

BACK_PORT="${BACK_PORT:-}"
VITE_PORT="${VITE_PORT:-}"

if [ -z "$BACK_PORT" ]; then BACK_PORT=$(find_free_port 8000 || echo 8001); fi
if [ -z "$VITE_PORT" ]; then VITE_PORT=$(find_free_port 8100 || echo 8190); fi

PDF_ROOT_ENV="${SERVER_PDFS_ROOT:-}"
if [ -z "$PDF_ROOT_ENV" ]; then
  if [ -d "data/input/pipeline" ]; then PDF_ROOT_ENV="${PWD}/data/input/pipeline";
  elif [ -d "prototypes/tabbed/pdfs" ]; then PDF_ROOT_ENV="${PWD}/prototypes/tabbed/pdfs";
  elif [ -d "data/pdfs" ]; then PDF_ROOT_ENV="${PWD}/data/pdfs"; else PDF_ROOT_ENV="${PWD}"; fi
fi

# Backend (FastAPI) — robust bind with fallback loop
start_backend() {
  local START="$1"; local PORT="$START"
  for PORT in $(seq "$START" $((START+50))); do
    if ss -ltn 2>/dev/null | grep -Eq ":${PORT}\\b"; then continue; fi
    SERVER_PDFS_ROOT="$PDF_ROOT_ENV" "$PY" -m uvicorn prototypes.tabbed.api.server:app --host 0.0.0.0 --port "$PORT" &
    BACK_PID=$!
    if wait_for_listen "$PORT" 40 0.25; then
      echo "$PORT"; return 0
    fi
    kill "$BACK_PID" 2>/dev/null || true; sleep 0.2 || true; kill -9 "$BACK_PID" 2>/dev/null || true
  done
  return 1
}

BACK_PORT=$(start_backend "$BACK_PORT") || BACK_PORT=$(start_backend 8000)
if [ -z "$BACK_PORT" ]; then echo "[req-dev] ERROR: Unable to bind backend" >&2; exit 2; fi

echo "[req-dev] Backend bound on :$BACK_PORT; starting Vite (desired :$VITE_PORT, proxy→:$BACK_PORT)"

# Frontend (Vite)
start_vite() {
  local WANT_PORT="$1"
  rm -rf prototypes/tabbed/html/.vite prototypes/tabbed/node_modules/.vite prototypes/tabbed/html/node_modules/.vite 2>/dev/null || true
  (
    cd prototypes/tabbed
    VITE_API_PROXY="http://127.0.0.1:$BACK_PORT" \
    npm run -w ./html dev -- --force --port "$WANT_PORT" --strictPort=false
  ) &
  VITE_PID=$!
  DETECTED_VITE_PORT=$(detect_vite_port "$WANT_PORT" 80 160 0.25 || echo "$WANT_PORT")
}

start_vite "$VITE_PORT"

OPEN_URL="http://127.0.0.1:${DETECTED_VITE_PORT}/main"
echo "[req-dev] Open: ${OPEN_URL}"

# Optional sanity check with Puppeteer (console errors and basic DOM markers)
if [ "${RUN_SANITY:-1}" = "1" ]; then
  echo "[req-dev] Running one-shot UI sanity smoke..."
  # Ensure a CDP endpoint for puppeteer-core
  CDP_PORT="${CDP_PORT:-9222}"
  DISC_URL="http://127.0.0.1:${CDP_PORT}/json/version"
  if ! curl -fsS --max-time 1 "$DISC_URL" >/dev/null 2>&1; then
    CHROME_BIN=""
    command -v google-chrome >/dev/null 2>&1 && CHROME_BIN="google-chrome"
    [ -z "$CHROME_BIN" ] && command -v chromium-browser >/dev/null 2>&1 && CHROME_BIN="chromium-browser"
    [ -z "$CHROME_BIN" ] && command -v chromium >/dev/null 2>&1 && CHROME_BIN="chromium"
    if [ -n "$CHROME_BIN" ]; then
      CDP_PROFILE=$(mktemp -d -t "chrome-cdp-profile-XXXXXX")
      "$CHROME_BIN" --headless=new --remote-debugging-address=127.0.0.1 --remote-debugging-port="$CDP_PORT" --disable-gpu --no-sandbox --user-data-dir="$CDP_PROFILE" about:blank >/dev/null 2>&1 &
      CDP_PID=$!
      # Wait up to ~5s for /json/version
      for i in $(seq 1 20); do curl -fsS --max-time 1 "$DISC_URL" >/dev/null 2>&1 && break; sleep 0.25; done
    fi
  fi
  export BROWSERLESS_DISCOVERY_URL="$DISC_URL"
  # Prefer CDP attach first to let the app fully warm up, then run console smoke
  if ! node scripts/ux_check_cdp_auto.mjs; then
    echo "[req-dev] Sanity FAIL (CDP attach). See scripts/artifacts/*.log and *.png" >&2
    exit 9
  fi
  if ! BASE_URL="$OPEN_URL" node scripts/smokes/console_errors.mjs; then
    echo "[req-dev] Sanity FAIL (console errors). Retrying after clearing Vite caches…" >&2
    kill ${VITE_PID:-} 2>/dev/null || true; sleep 0.5 || true
    VITE_PORT=$((DETECTED_VITE_PORT+1))
    start_vite "$VITE_PORT"
    OPEN_URL="http://127.0.0.1:${DETECTED_VITE_PORT}/main"
    echo "[req-dev] Open: ${OPEN_URL} (retry)" >&2
    if ! node scripts/ux_check_cdp_auto.mjs; then
      echo "[req-dev] Sanity FAIL (CDP attach retry)." >&2; exit 9
    fi
    if ! BASE_URL="$OPEN_URL" node scripts/smokes/console_errors.mjs; then
      echo "[req-dev] Sanity FAIL after retry. See scripts/artifacts/*.log and *.png" >&2
      exit 9
    fi
  fi
  # DOM count smoke for requirements pane
  if ! BASE_URL="http://127.0.0.1:${DETECTED_VITE_PORT}" node scripts/smokes/ui_requirements_pane_dom.mjs; then
    echo "[req-dev] Sanity WARN: requirements pane DOM check failed (continuing)." >&2
  fi
  # Inspector + Zoom buttons (non-blocking warns)
  if ! BASE_URL="http://127.0.0.1:${DETECTED_VITE_PORT}" node scripts/smokes/ui_inspector_pane_present.mjs; then
    echo "[req-dev] Sanity WARN: inspector pane check failed (continuing)." >&2
  fi
  if ! BASE_URL="http://127.0.0.1:${DETECTED_VITE_PORT}" node scripts/smokes/ui_zoom_buttons_present.mjs; then
    echo "[req-dev] Sanity WARN: zoom buttons check failed (continuing)." >&2
  fi
  # Tooltips (advisory)
  if ! BASE_URL="http://127.0.0.1:${DETECTED_VITE_PORT}" node scripts/smokes/ui_toolbar_tooltips.mjs; then
    echo "[req-dev] Sanity WARN: toolbar tooltips check failed (continuing)." >&2
  fi
fi

cleanup(){ echo "[req-dev] Stopping..."; kill ${BACK_PID:-} ${VITE_PID:-} 2>/dev/null || true; }
trap cleanup EXIT INT TERM

wait $BACK_PID $VITE_PID
