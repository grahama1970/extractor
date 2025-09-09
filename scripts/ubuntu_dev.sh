#!/usr/bin/env bash
set -euo pipefail

# Single-command launcher with sane defaults.
# Starts the app on 127.0.0.1:3012 and Chromium headless with DevTools on 127.0.0.1:9222

APP_DIR="${APP_DIR:-$HOME/workspace/experiments/extractor/tools/gold_annotator_2}"
APP_PORT="${APP_PORT:-3012}"
RD_PORT="${RD_PORT:-9222}"
CHROME_LOG="${CHROME_LOG:-/tmp/chrome.log}"

log() { printf "\033[1;34m[ubuntu_dev]\033[0m %s\n" "$*"; }
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1" >&2; exit 1; }; }

need curl

detect_chrome() {
  for b in chromium chromium-browser google-chrome; do
    command -v "$b" >/dev/null 2>&1 && { echo "$b"; return 0; }
  done
  echo "ERROR: chromium not found; install: sudo snap install chromium" >&2
  exit 1
}

CHROME_BIN="${CHROME_BIN:-$(detect_chrome)}"

if [[ ! -d "$APP_DIR" ]]; then
  echo "ERROR: APP_DIR not found: $APP_DIR" >&2
  exit 1
fi

log "App dir: $APP_DIR"
cd "$APP_DIR"

# Ensure pdf.js worker
if [[ -f node_modules/pdfjs-dist/build/pdf.worker.min.mjs ]]; then
  mkdir -p public
  cp -f node_modules/pdfjs-dist/build/pdf.worker.min.mjs public/pdf.worker.min.js || true
fi

# Install deps if missing
if [[ ! -d node_modules ]]; then
  log "Installing deps…"
  npm i
fi

# Kill any old Next dev from this dir (best effort)
pkill -f "$APP_DIR/node_modules/.bin/next" >/dev/null 2>&1 || true

# Start Next dev on loopback
log "Starting app: http://127.0.0.1:$APP_PORT"
nohup npm run dev -- -H 127.0.0.1 -p "$APP_PORT" > /tmp/app.dev.log 2>&1 &
sleep 1

# Wait for app to respond
for i in {1..40}; do
  if curl -fs "http://127.0.0.1:$APP_PORT" >/dev/null 2>&1; then
    log "App OK"
    break
  fi
  sleep 0.5
  [[ $i -eq 40 ]] && { echo "WARN: App not responding yet" >&2; }
done

# Start Chromium headless RD and open the app tab
log "Starting $CHROME_BIN headless RD on 127.0.0.1:$RD_PORT (log: $CHROME_LOG)"
pkill -f "remote-debugging.*$RD_PORT" >/dev/null 2>&1 || true
"$CHROME_BIN" --headless=new \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port="$RD_PORT" \
  --user-data-dir=/tmp/chrome-rd \
  "http://127.0.0.1:$APP_PORT" \
  >"$CHROME_LOG" 2>&1 &

# Wait for RD
for i in {1..40}; do
  if curl -fs "http://127.0.0.1:$RD_PORT/json/version" >/dev/null 2>&1; then
    log "CDP OK"
    break
  fi
  sleep 0.5
  [[ $i -eq 40 ]] && { echo "WARN: RD not responding yet" >&2; }
done

# Show brief status
log "RD version:"; curl -s "http://127.0.0.1:$RD_PORT/json/version" | sed -n '1,5p' || true
log "Targets:"; curl -s "http://127.0.0.1:$RD_PORT/json/list" | sed -n '1,5p' || true
log "Logs: app=/tmp/app.dev.log chrome=$CHROME_LOG"
