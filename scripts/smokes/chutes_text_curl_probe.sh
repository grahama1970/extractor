#!/usr/bin/env bash
# One‑shot OpenAI‑compatible text JSON curl probe against Chutes.
set -euo pipefail

ART_DIR="scripts/artifacts"
mkdir -p "$ART_DIR"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
set -a
[[ -f .env ]] && source .env || true
set +a

require() { local n=$1; local v=${!1:-}; if [[ -z ${v// } ]]; then echo "[probe] Missing $n" >&2; exit 2; fi; }
require CHUTES_API_BASE
require CHUTES_API_KEY
MODEL=${CHUTES_TEXT_MODEL:-}
require MODEL

cat > "$ART_DIR/chutes_text_probe.payload.json" <<JSON
{
  "model": "${MODEL}",
  "messages": [
    {"role":"system","content":"You are precise. Return only JSON; no code fences."},
    {"role":"user","content":"Return only {\"ok\": true, \"note\": string} as JSON."}
  ],
  "response_format": {"type":"json_object"},
  "max_tokens": 64,
  "temperature": 0
}
JSON

curl -sS \
  -D "$ART_DIR/chutes_text_probe.headers.txt" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $CHUTES_API_KEY" \
  -H "x-api-key: $CHUTES_API_KEY" \
  -o "$ART_DIR/chutes_text_probe.response.json" \
  "$CHUTES_API_BASE/chat/completions" \
  --data @"$ART_DIR/chutes_text_probe.payload.json"

python - <<'PY'
import json, re, sys
from pathlib import Path
head = Path('scripts/artifacts/chutes_text_probe.headers.txt').read_text('utf-8', errors='ignore')
resp_t = Path('scripts/artifacts/chutes_text_probe.response.json').read_text('utf-8', errors='ignore')
try:
    resp = json.loads(resp_t or '{}')
except Exception:
    print('[probe] Response not JSON')
    sys.exit(10)
m = re.search(r'^HTTP/\S+\s+(\d+)', head, re.M)
status = int(m.group(1)) if m else 0
content = (resp.get('choices') or [{}])[0].get('message',{}).get('content')
data = {}
if isinstance(content, str):
    try:
        data = json.loads(content)
    except Exception:
        data = {}
elif isinstance(content, dict):
    data = content
ok = (data.get('ok') is True)
note = data.get('note')
out = {"http_status": status, "ok": ok, "has_note": bool(note), "note_preview": (note or '')[:120]}
Path('scripts/artifacts/chutes_text_probe.summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(json.dumps(out, indent=2))
sys.exit(0 if status==200 and ok and note else 1)
PY

echo "[probe] Artifacts:"
printf " - %s\n" \
  "$ART_DIR/chutes_text_probe.payload.json" \
  "$ART_DIR/chutes_text_probe.headers.txt" \
  "$ART_DIR/chutes_text_probe.response.json" \
  "$ART_DIR/chutes_text_probe.summary.json"

