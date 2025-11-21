#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate && \
set -a && [ -f .env ] && source .env && set +a && \
curl -sS \ 
  -w '\nHTTP_STATUS=%{http_code}\n' \
  -H "Authorization: Bearer $CHUTES_API_KEY" \
  -H 'Content-Type: application/json' \
  "$CHUTES_API_BASE/chat/completions" \
  -d '{
    "model": "'"$CHUTES_TEXT_MODEL"'",
    "messages": [
      {"role": "user", "content": "Return only {\"ok\":true} as JSON."}
    ],
    "response_format": {"type": "json_object"},
    "temperature": 0,
    "max_tokens": 16
  }'