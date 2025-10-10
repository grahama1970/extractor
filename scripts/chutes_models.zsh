#!/usr/bin/env zsh
set -euo pipefail

# Non-destructive Chutes model discovery helper.
# - Reads CHUTES_API_BASE and CHUTES_API_KEY
# - Writes:
#     .artifacts/chutes/models_raw.json
#     .artifacts/chutes/models_ids.txt
#     .artifacts/chutes/id_map.json  (alias → canonical, e.g., openai/<id> → <id>)
# - Usage:
#     export CHUTES_API_BASE="https://llm.chutes.ai/v1"
#     export CHUTES_API_KEY="..."
#     scripts/chutes_models.zsh --print

function usage() {
  echo "Usage: $0 [--print]" >&2
}

PRINT=0
if [[ ${#@} -gt 0 ]]; then
  if [[ "$1" == "--print" ]]; then
    PRINT=1
  else
    usage; exit 2
  fi
fi

if [[ -z "${CHUTES_API_BASE:-}" ]]; then
  echo "CHUTES_API_BASE required" >&2; exit 1
fi
if [[ -z "${CHUTES_API_KEY:-}" ]]; then
  echo "CHUTES_API_KEY required" >&2; exit 1
fi

ART=".artifacts/chutes"
RAW="$ART/models_raw.json"
IDS="$ART/models_ids.txt"
MAP="$ART/id_map.json"
mkdir -p "$ART"

BASE="${CHUTES_API_BASE%/}"
URL="$BASE/models"

# Fetch raw JSON
if command -v curl >/dev/null 2>&1; then
  curl -sS -H "Authorization: Bearer ${CHUTES_API_KEY}" "$URL" > "$RAW"
else
  python3 - <<'PY' > "$RAW"
import json, os, sys, urllib.request
base=os.environ.get('CHUTES_API_BASE','').rstrip('/')
key=os.environ.get('CHUTES_API_KEY','')
req=urllib.request.Request(base+'/models', headers={'Authorization': f'Bearer {key}','Content-Type':'application/json'})
with urllib.request.urlopen(req, timeout=20) as r:
    sys.stdout.write(r.read().decode('utf-8'))
PY
fi

# Extract IDs
if command -v jq >/dev/null 2>&1; then
  jq -r '.data[]?.id // empty' "$RAW" > "$IDS" || true
else
  python3 - "$RAW" "$IDS" <<'PY'
import json,sys
src,dst=sys.argv[1],sys.argv[2]
ids=[]
try:
    data=json.load(open(src,'r',encoding='utf-8'))
    for x in (data.get('data') or []):
        i=x.get('id')
        if i: ids.append(i)
except Exception:
    pass
open(dst,'w',encoding='utf-8').write('\n'.join(ids))
PY
fi

# Build a tiny alias→canonical map (openai/<id> → <id>)
python3 - "$IDS" "$MAP" <<'PY'
import json,sys
ids_path, map_path = sys.argv[1], sys.argv[2]
try:
    ids=[x.strip() for x in open(ids_path,'r',encoding='utf-8').read().splitlines() if x.strip()]
except Exception:
    ids=[]
alias={}
for mid in ids:
    alias[f"openai/{mid}"]=mid
json.dump(alias, open(map_path,'w',encoding='utf-8'), indent=2)
PY

echo "[ok] wrote $RAW"
echo "[ok] wrote $IDS (count: $(wc -l < "$IDS" | tr -d ' '))"
echo "[ok] wrote $MAP"

if [[ $PRINT -eq 1 ]]; then
  echo "[first 40 ids]"; head -n 40 "$IDS" || true
fi

