#!/usr/bin/env bash
set -euo pipefail
# S5: SciLLM/Chutes minimal call sanity via Curl

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
    source .env
fi

if [ -z "${CHUTES_API_TOKEN:-}" ]; then
    if [ -z "${CHUTES_API_KEY:-}" ]; then
        echo "ERROR: CHUTES_API_TOKEN or CHUTES_API_KEY not set." >&2
        exit 1
    fi
    CHUTES_API_TOKEN="$CHUTES_API_KEY"
fi

echo "Testing Chutes connection..."
RESPONSE=$(curl -s -X POST https://llm.chutes.ai/v1/chat/completions \
    -H "Authorization: Bearer $CHUTES_API_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "Qwen/Qwen3-VL-235B-A22B-Instruct",
      "messages": [
        {
          "role": "user",
          "content": "Tell me a 5 word story."
        }
      ],
      "stream": false,
      "max_tokens": 10,
      "temperature": 0.7
    }')

if echo "$RESPONSE" | grep -q "choices"; then
    echo "OK: S5_scillm_min_call"
    exit 0
else
    echo "ERROR: Chutes call failed." >&2
    echo "Response: $RESPONSE" >&2
    exit 1
fi
