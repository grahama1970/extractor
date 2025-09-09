#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$ROOT_DIR"

# Ensure Puppeteer available
if [ ! -f package.json ]; then npm init -y >/dev/null 2>&1 || true; fi
npm i -D puppeteer >/dev/null 2>&1 || true

# Start dev server
pushd prototypes/tabbed/html >/dev/null
if ! command -v npm >/dev/null; then echo "npm missing" >&2; exit 1; fi
npm install >/dev/null 2>&1 || true
PORT=8080
(npm run -s dev >/tmp/proto_dev.log 2>&1 &) 
popd >/dev/null

# Wait for server
for i in $(seq 1 120); do
  if curl -sSf "http://127.0.0.1:${PORT}/main" >/dev/null 2>&1 || curl -sSf "http://127.0.0.1:${PORT}/classic" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

node scripts/ux_suite.mjs
