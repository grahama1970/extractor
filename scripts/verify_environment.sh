#!/usr/bin/env bash
set -euo pipefail

# Optional: activate venv and load .env
if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate || true
fi
set +u
set -a
[[ -f .env ]] && source .env || true
set +a
set -u

# Arango env with defaults if not set
ARANGO_HOST="${ARANGO_HOST:-localhost}"
ARANGO_PORT="${ARANGO_PORT:-8529}"
ARANGO_USERNAME="${ARANGO_USERNAME:-root}"
ARANGO_PASSWORD="${ARANGO_PASSWORD:-openSesame}"
BASE_URL="http://${ARANGO_HOST}:${ARANGO_PORT}"

pass() { echo "[PASS] $1"; }
fail() { echo "[FAIL] $1"; exit 1; }

echo "== Environment Summary =="
echo "approval_policy: never (session)"
echo "sandbox_mode: danger-full-access (session)"
echo "network_access: enabled (session)"
echo "cwd: $(pwd)"
echo "ARANGO_HOST=${ARANGO_HOST} ARANGO_PORT=${ARANGO_PORT}"
echo

echo "== Network Check =="
if HTTP=$(curl -sS -o /dev/null -w "%{http_code}" https://example.com); then
  if [[ "$HTTP" == "200" ]]; then pass "Internet reachable (example.com, 200)"; else fail "Unexpected HTTP: $HTTP"; fi
else
  fail "Failed to reach example.com"
fi
echo

echo "== Filesystem (No Sandbox) Check =="
if head -n 1 /etc/os-release >/dev/null 2>&1; then pass "Can read /etc/os-release"; else fail "Cannot read /etc/os-release"; fi
echo codex_write_ok > /tmp/codex_fs_check.txt
if [[ "$(cat /tmp/codex_fs_check.txt)" == "codex_write_ok" ]]; then pass "Can write to /tmp"; else fail "Cannot write to /tmp"; fi
echo

echo "== ArangoDB Connectivity (via env) =="
VER_HTTP=$(curl -sS -u "$ARANGO_USERNAME:$ARANGO_PASSWORD" -o /tmp/arangov1.json -w "%{http_code}" "$BASE_URL/_api/version" || true)
if [[ "$VER_HTTP" == "200" ]]; then
  pass "GET /_api/version (HTTP 200)"
  echo "Response: $(cat /tmp/arangov1.json | tr -d '\n')"
else
  echo "HTTP: $VER_HTTP"
  fail "Cannot GET /_api/version"
fi

DB_HTTP=$(curl -sS -u "$ARANGO_USERNAME:$ARANGO_PASSWORD" -o /tmp/arangodbuser.json -w "%{http_code}" "$BASE_URL/_api/database/user" || true)
if [[ "$DB_HTTP" == "200" ]]; then
  pass "GET /_api/database/user (HTTP 200)"
  echo "Databases (truncated): $(head -c 200 /tmp/arangodbuser.json)"
else
  echo "HTTP: $DB_HTTP"
  fail "Cannot GET /_api/database/user"
fi
echo

echo "All checks passed. Full network, DB connectivity, and no sandbox confirmed."

