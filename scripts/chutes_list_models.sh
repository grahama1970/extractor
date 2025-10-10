#!/usr/bin/env bash
set -euo pipefail
: "${CHUTES_API_BASE:?CHUTES_API_BASE required}"
: "${CHUTES_API_KEY:?CHUTES_API_KEY required}"
out=".artifacts/chutes/models.json"
mkdir -p ".artifacts/chutes"
curl -sS -H "Authorization: Bearer ${CHUTES_API_KEY}" "${CHUTES_API_BASE%/}/models" | jq . > "${out}"
echo "[ok] wrote ${out}"
echo "[vlm candidates]"
jq -r '.data[].id' "${out}" | egrep -i 'vl|vision|gpt-4o|qwen-vl|kimi-vl' || true

