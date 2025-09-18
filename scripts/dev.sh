#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Robust port killer (IPv4/IPv6; fuser/lsof/ss fallback)
kill_port() {
  local PORT="$1"
  echo "[dev] Ensuring port ${PORT} is free..."
  # Try fuser first
  if command -v fuser >/dev/null 2>&1; then
    fuser -k -TERM "${PORT}/tcp" 2>/dev/null || true
    sleep 0.2 || true
    fuser -k -KILL "${PORT}/tcp" 2>/dev/null || true
  fi
  # Try lsof (LISTEN only)
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids=$(lsof -ti tcp:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "${pids}" ]; then
      echo "[dev] Killing PIDs on :${PORT}: ${pids}"
      kill ${pids} 2>/dev/null || true
      sleep 0.2 || true
      kill -9 ${pids} 2>/dev/null || true
    fi
  fi
  # Parse PIDs from ss output (filter by the exact port line)
  if command -v ss >/dev/null 2>&1; then
    local ss_out
    ss_out=$(ss -ltnp 2>/dev/null | awk -v p=":${PORT}" 'index($0,p)>0 { print }' || true)
    if [ -n "${ss_out}" ]; then
      local ss_pids
      ss_pids=$(printf "%s" "${ss_out}" | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | sort -u)
      if [ -n "${ss_pids}" ]; then
        echo "[dev] Killing PIDs from ss on :${PORT}: ${ss_pids}"
        kill ${ss_pids} 2>/dev/null || true
        sleep 0.2 || true
        kill -9 ${ss_pids} 2>/dev/null || true
      fi
    fi
  fi
}

find_free_port() {
  # Prefer 8000 first to match Vite's default proxy target
  local candidates=(8000 8001 8011 8012 8013 8014 8015)
  for port in "${candidates[@]}"; do
    if ! ss -ltn 2>/dev/null | grep -Eq ":${port}\\b"; then
      echo "$port"; return 0
    fi
  done
  for port in $(seq 8020 8050); do
    if ! ss -ltn 2>/dev/null | grep -Eq ":${port}\\b"; then
      echo "$port"; return 0
    fi
  done
  return 1
}

# Poll until a port is LISTENing. Usage: wait_for_listen PORT [TRIES] [SLEEP]
wait_for_listen() {
  local PORT="$1"; local TRIES="${2:-14}"; local DELAY="${3:-0.5}"
  local i=0
  while [ "$i" -lt "$TRIES" ]; do
    if ss -ltn 2>/dev/null | grep -Eq ":${PORT}\\b"; then return 0; fi
    sleep "$DELAY" || true
    i=$((i+1))
  done
  return 1
}

wait_for_http() {
  local URL="$1"; local TRIES="${2:-20}"; local DELAY="${3:-0.5}"
  local i=0
  while [ "$i" -lt "$TRIES" ]; do
    if curl -fsS --max-time 2 "$URL" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$DELAY" || true
    i=$((i+1))
  done
  return 1
}

warm_url() {
  local URL="$1"; local TRIES="${2:-30}"; local DELAY="${3:-0.5}"
  local i=0
  while [ "$i" -lt "$TRIES" ]; do
    if curl -fsS --max-time 4 "$URL" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$DELAY" || true
    i=$((i+1))
  done
  return 1
}

launch_console_sanity() {
  local BASE_URL="$1"
  local DEFAULT_DISC="$2"

  (
    DEV_CDP_AUTOLAUNCH_VAL="${DEV_CDP_AUTOLAUNCH:-0}"
    DEV_CDP_FORCE_REMOTE_VAL="${DEV_CDP_FORCE_REMOTE:-0}"
    DEV_CDP_PORT_VAL="${DEV_CDP_PORT:-9222}"
    DISC_URL="$DEFAULT_DISC"
    LOCAL_CHROME_PID=""
    LOCAL_CHROME_PROFILE=""
    CHROME_BIN="${DEV_CDP_CHROME_BIN:-}"

    if [ -z "$CHROME_BIN" ]; then
      if command -v google-chrome >/dev/null 2>&1; then
        CHROME_BIN="google-chrome"
      elif command -v chromium-browser >/dev/null 2>&1; then
        CHROME_BIN="chromium-browser"
      else
        CHROME_BIN=""
      fi
    fi

    cleanup_local_chrome() {
      if [ -n "${LOCAL_CHROME_PID:-}" ]; then
        kill "${LOCAL_CHROME_PID}" 2>/dev/null || true
        wait "${LOCAL_CHROME_PID}" 2>/dev/null || true
        LOCAL_CHROME_PID=""
      fi
      if [ -n "${LOCAL_CHROME_PROFILE:-}" ]; then
        rm -rf "${LOCAL_CHROME_PROFILE}" 2>/dev/null || true
        LOCAL_CHROME_PROFILE=""
      fi
    }

    autolaunch_local_chrome() {
      local PORT="$1"
      if [ -z "$CHROME_BIN" ]; then
        return 1
      fi
      local LOG_FILE
      LOG_FILE=$(mktemp -t "chrome_cdp_${PORT}_XXXX.log")
      LOCAL_CHROME_PROFILE=$(mktemp -d -t "chrome-cdp-profile-XXXXXX")
      echo "[dev] Autolaunching headless Chrome on :${PORT} for CDP sanity (log: $LOG_FILE)"
      "$CHROME_BIN" \
        --headless=new \
        --remote-debugging-address=127.0.0.1 \
        --remote-debugging-port="$PORT" \
        --disable-gpu \
        --no-sandbox \
        --no-first-run \
        --no-default-browser-check \
        --user-data-dir="$LOCAL_CHROME_PROFILE" \
        about:blank >"$LOG_FILE" 2>&1 &
      LOCAL_CHROME_PID=$!
      if wait_for_http "http://127.0.0.1:${PORT}/json/version" 40 0.5; then
        DISC_URL="http://127.0.0.1:${PORT}/json/version"
        return 0
      fi
      echo "[dev] WARN: Local Chrome CDP not reachable on :${PORT}; check $LOG_FILE" >&2
      cleanup_local_chrome
      return 1
    }

    trap cleanup_local_chrome EXIT INT TERM

    if [ "$DEV_CDP_AUTOLAUNCH_VAL" = "1" ] && [ "$DEV_CDP_FORCE_REMOTE_VAL" != "1" ] && [ -n "$CHROME_BIN" ]; then
      autolaunch_local_chrome "$DEV_CDP_PORT_VAL" || DISC_URL="$DEFAULT_DISC"
    fi

    if [ -z "$LOCAL_CHROME_PID" ]; then
      if [ "$DEV_CDP_AUTOLAUNCH_VAL" = "1" ] && [ -n "$CHROME_BIN" ] && ! curl -fsS --max-time 1 "$DEFAULT_DISC" >/dev/null 2>&1; then
        echo "[dev] CDP discovery not responding ($DEFAULT_DISC). Autolaunching headless Chrome locally..."
        autolaunch_local_chrome "$DEV_CDP_PORT_VAL" || DISC_URL="$DEFAULT_DISC"
      else
        DISC_URL="$DEFAULT_DISC"
      fi
    fi

    echo "[dev] DEV_CDP_SANITY=1 — will run one-shot console error smoke in ~3s (DISCOVERY=$DISC_URL)"

    sleep 3
    if ! wait_for_http "$BASE_URL" 40 0.5; then
      echo "[dev] WARN: Vite dev server not reachable at $BASE_URL before console error smoke" >&2
    fi
    if ! warm_url "$BASE_URL/@vite/client" 40 0.5; then
      echo "[dev] WARN: Unable to warm Vite client script at $BASE_URL/@vite/client" >&2
    fi
    if ! warm_url "$BASE_URL/classic" 40 0.5; then
      echo "[dev] WARN: Unable to warm classic route at $BASE_URL/classic" >&2
    fi

    BASE_URL="$BASE_URL" \
    BROWSERLESS_DISCOVERY_URL="$DISC_URL" \
    node "$ROOT_DIR/scripts/smokes/console_errors.mjs" || true
  ) &
}

# Make stale dev/preview servers impossible by killing ports first
echo "[dev] Killing ports 8080 and 8001 (if any)..."
kill_port 8080
kill_port 8001

echo "[dev] Cleaning Vite transform cache (if present)..."
rm -rf \
  prototypes/tabbed/node_modules/.vite \
  prototypes/tabbed/html/node_modules/.vite \
  prototypes/tabbed/html/.vite 2>/dev/null || true

PY="${VENV_PY:-${PWD}/.venv/bin/python}"
if [ ! -x "$PY" ]; then
  PY="python"
fi
# If uvicorn isn't available in the chosen interpreter, fallback to system python if it has it
if ! "$PY" -c 'import uvicorn' >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1 && python -c 'import uvicorn' >/dev/null 2>&1; then
    echo "[dev] uvicorn not found in $PY; falling back to system python"
    PY="python"
  else
    echo "[dev] WARN: uvicorn not installed in $PY. Consider running 'make setup' (installs dev deps) or 'python -m pip install uvicorn fastapi'." >&2
  fi
fi

echo "[dev] Python: $($PY -c 'import sys; print(sys.executable)')"
UVV=$($PY -c 'import sys; print(getattr(__import__("uvicorn"), "__version__", "(missing)"))' 2>/dev/null || echo "(missing)")
echo "[dev] uvicorn version: $UVV"

# Ensure workspace deps are installed (hoisted at prototypes/tabbed/node_modules)
TAB_DIR="prototypes/tabbed"
if [ -d "$TAB_DIR" ]; then
  if [ ! -d "$TAB_DIR/node_modules" ] || [ -z "$(ls -A "$TAB_DIR/node_modules" 2>/dev/null)" ]; then
    echo "[dev] Installing workspace dependencies at $TAB_DIR ..."
    ( cd "$TAB_DIR" && npm install --no-fund --no-audit )
  else
    echo "[dev] Dependencies detected at $TAB_DIR/node_modules — skipping install"
  fi
fi

INIT_BACK_PORT="${BACK_PORT:-}"
BACK_PORT="$INIT_BACK_PORT"
if [ -z "$BACK_PORT" ]; then
  BACK_PORT=$(find_free_port || echo 8001)
fi
PDF_ROOT_ENV="${SERVER_PDFS_ROOT:-}"
if [ -z "$PDF_ROOT_ENV" ]; then
  if [ -d "prototypes/tabbed/pdfs" ]; then
    PDF_ROOT_ENV="${PWD}/prototypes/tabbed/pdfs"
  elif [ -d "data/pdfs" ]; then
    PDF_ROOT_ENV="${PWD}/data/pdfs"
  else
    PDF_ROOT_ENV="${PWD}"
  fi
fi
echo "[dev] Starting FastAPI backend on :$BACK_PORT (SERVER_PDFS_ROOT=$PDF_ROOT_ENV)..."
if [ -f "prototypes/tabbed/api/server.py" ]; then
  echo "[dev] Using self-contained tabbed API"
  SERVER_PDFS_ROOT="$PDF_ROOT_ENV" "$PY" -m uvicorn prototypes.tabbed.api.server:app --host 0.0.0.0 --port "$BACK_PORT" &
else
  SERVER_PDFS_ROOT="$PDF_ROOT_ENV" "$PY" -m uvicorn extractor.core.scripts.server:app --host 0.0.0.0 --port "$BACK_PORT" &
fi
BACK_PID=$!

# Final sanity: wait for bind; otherwise, attempt fallback once
if ! wait_for_listen "$BACK_PORT" 16 0.4; then
  echo "[dev] WARN: Backend not listening on :${BACK_PORT}. Attempting fallback..." >&2
  # Kill attempted backend
  kill "$BACK_PID" 2>/dev/null || true
  sleep 0.2 || true
  kill -9 "$BACK_PID" 2>/dev/null || true

  # Choose another free port dynamically (avoid reusing the same port if possible)
  CUR_PORT="$BACK_PORT"
  BACK_PORT=$(find_free_port || echo 8000)
  if [ "$BACK_PORT" = "$CUR_PORT" ]; then
    BACK_PORT=8000
  fi
  echo "[dev] Starting FastAPI backend on :$BACK_PORT (fallback)"
  if [ -f "prototypes/tabbed/api/server.py" ]; then
    SERVER_PDFS_ROOT="$PDF_ROOT_ENV" "$PY" -m uvicorn prototypes.tabbed.api.server:app --host 0.0.0.0 --port "$BACK_PORT" &
  else
    SERVER_PDFS_ROOT="$PDF_ROOT_ENV" "$PY" -m uvicorn extractor.core.scripts.server:app --host 0.0.0.0 --port "$BACK_PORT" &
  fi
  BACK_PID=$!
  if ! wait_for_listen "$BACK_PORT" 16 0.4; then
    echo "[dev] WARN: Backend bind not confirmed after fallback; continuing. Diagnostics:" >&2
    (command -v ss >/dev/null 2>&1 && ss -ltnp || true) >&2
    (command -v ps >/dev/null 2>&1 && ps aux | grep -E "uvicorn|prototypes.tabbed.api.server|extractor.core.scripts.server" -- || true) >&2
  fi
fi

# Print backend sanity and selected proxy
API_BASE="http://127.0.0.1:${BACK_PORT}"
echo "[dev] Backend candidate: $API_BASE"
if command -v curl >/dev/null 2>&1; then
  BUILD_JSON=$(curl -fsS --max-time 2 "$API_BASE/api/build" 2>/dev/null || true)
  if [ -n "$BUILD_JSON" ]; then
    echo "[dev] Backend OK at $API_BASE (build: $(echo "$BUILD_JSON" | sed -n 's/.*\"git\":\s*\"\([^"]*\)\".*/\1/p'))"
  else
    echo "[dev] WARN: Backend /api/build not reachable at $API_BASE"
  fi
fi

cleanup() {
  echo "[dev] Cleaning up..."
  kill $BACK_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[dev] Starting Vite dev server on :8080 with --force... (proxy→http://127.0.0.1:$BACK_PORT)"
if [ -d "prototypes/tabbed/html" ]; then
  # Use npm workspaces so node_modules live in prototypes/tabbed/
  if [ -f "prototypes/tabbed/package.json" ]; then
    (
      cd prototypes/tabbed && \
      VITE_API_PROXY="${VITE_API_PROXY:-http://127.0.0.1:$BACK_PORT}" npm run -w ./html dev -- --force &
      VITE_PID=$!
      # Optional: auto-launch CDP and run one-shot console error smoke
      if [ "${DEV_CDP_SANITY:-0}" = "1" ]; then
        DEFAULT_DISC="${BROWSERLESS_DISCOVERY_URL:-http://127.0.0.1:3000/json/version}"
        launch_console_sanity "http://127.0.0.1:8080" "$DEFAULT_DISC"
      fi
      wait "$VITE_PID"
    )
  else
    (
      cd prototypes/tabbed/html && \
      VITE_API_PROXY="${VITE_API_PROXY:-http://127.0.0.1:$BACK_PORT}" npm run dev -- --force &
      VITE_PID=$!
      if [ "${DEV_CDP_SANITY:-0}" = "1" ]; then
        DEFAULT_DISC="${BROWSERLESS_DISCOVERY_URL:-http://127.0.0.1:3000/json/version}"
        launch_console_sanity "http://127.0.0.1:8080" "$DEFAULT_DISC"
      fi
      wait "$VITE_PID"
    )
  fi
else
  echo "[dev] WARNING: prototypes/tabbed/html not found. Please adjust script paths."
  # Fallback: keep backend running so task doesn't exit immediately
  wait $BACK_PID
fi
