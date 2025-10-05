#!/usr/bin/env bash
set -euo pipefail

usage() { echo "Usage: $0 --model <id> [--text 'ping']"; exit 1; }
MODEL=""; TEXT="ping"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2;;
    --text) TEXT="$2"; shift 2;;
    *) usage;;
  esac
done
[[ -n "$MODEL" ]] || usage

[[ "/.venv/bin" == *"$(python -c 'import sys; print(sys.executable)')"* ]] || {
  echo "ERROR: Not in project venv. Run: source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a" >&2; exit 2; }

: "${CHUTES_API_BASE:?Missing CHUTES_API_BASE}"; : "${CHUTES_API_KEY:?Missing CHUTES_API_KEY}"
BASE="${CHUTES_API_BASE%/}"

curl -sS -H "Authorization: Bearer $CHUTES_API_KEY" -H 'Content-Type: application/json' \
  "$BASE/chat/completions" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":[{\"type\":\"text\",\"text\":\"$TEXT\"}]}],\"temperature\":0}" | jq .

