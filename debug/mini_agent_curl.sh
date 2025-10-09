#!/usr/bin/env bash
set -euo pipefail
BASE="${MINI_AGENT_BASE:-http://127.0.0.1:18077}"
echo "GET $BASE/ready" >&2
curl -sS "$BASE/ready" | jq .
echo "POST $BASE/agent/run" >&2
curl -sS -H 'Content-Type: application/json' -d '{"tool_backend":"local"}' "$BASE/agent/run" | jq .

