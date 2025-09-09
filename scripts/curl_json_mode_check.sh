#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-gpt-4o-mini}"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY not set in current shell. export OPENAI_API_KEY=sk-..." >&2
  exit 1
fi

echo "Testing JSON mode with model: ${MODEL}" >&2
HTTP=$(curl -sS -o /tmp/oai_resp.json -w "HTTP_STATUS:%{http_code}\n" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/chat/completions \
  -d "{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"Return only {\\\"ok\\\":true} as JSON.\"}],\"response_format\":{\"type\":\"json_object\"},\"max_tokens\":20}")
echo "$HTTP"
echo "--- Body ---"
if command -v jq >/dev/null 2>&1; then
  jq . /tmp/oai_resp.json || cat /tmp/oai_resp.json
else
  cat /tmp/oai_resp.json
fi

