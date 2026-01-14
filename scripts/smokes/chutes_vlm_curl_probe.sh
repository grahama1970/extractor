#!/usr/bin/env bash
# One‑shot OpenAI‑compatible multimodal curl probe against Chutes.
# - Activates venv, loads .env
# - Finds a section image from 04_section_builder or 06b; if missing, renders a temp PNG from the first page of the sample PDF
# - Builds JSON payload with base64 image and posts to $CHUTES_API_BASE/chat/completions
# - Saves artifacts under scripts/artifacts/ and prints a concise summary
# - Exits non‑zero if HTTP!=200 or JSON lacks {ok, caption}

set -euo pipefail
shopt -s globstar nullglob

ART_DIR="scripts/artifacts"
mkdir -p "$ART_DIR"

# 1) Activate env + load .env
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
set -a
[[ -f .env ]] && source .env || true
set +a

require() {
  local name=$1; local val=${!1:-}
  if [[ -z ${val// } ]]; then
    echo "[probe] Missing required env: $name" >&2
    exit 2
  fi
}

require CHUTES_API_BASE
require CHUTES_API_KEY

# Prefer vision model, fall back to text model if not set
MODEL=${CHUTES_VLM_MODEL:-${CHUTES_TEXT_MODEL:-}}
require MODEL

# 2) Locate a section image; fall back to a quick render if none found
IMG_PATH=""
for p in data/results/**/04_section_builder/visual_output/section_*.png; do IMG_PATH=$p; break; done
if [[ -z "$IMG_PATH" ]]; then
  for p in data/results/**/06b_layout_sketcher/visual/section_*.png; do IMG_PATH=$p; break; done
fi
if [[ -z "$IMG_PATH" ]]; then
  # Try to render first page from a likely sample PDF
  CAND_PDF=${1:-data/input/pipeline/BHT_CV32A65X_with_requirements.pdf}
  if [[ -f "$CAND_PDF" ]]; then
    python - <<'PY'
import sys, os
try:
    import fitz  # PyMuPDF
except Exception as e:
    print(f"[probe] PyMuPDF not available: {e}", file=sys.stderr)
    sys.exit(3)
pdf = os.environ.get('CAND_PDF','data/input/pipeline/BHT_CV32A65X_with_requirements.pdf')
out = 'scripts/artifacts/temp_section.png'
doc = fitz.open(pdf)
page = doc[0]
mat = fitz.Matrix(2,2)
pix = page.get_pixmap(matrix=mat, alpha=False)
pix.save(out)
doc.close()
print(out)
PY
    IMG_PATH="$ART_DIR/temp_section.png"
  fi
fi
if [[ -z "$IMG_PATH" || ! -f "$IMG_PATH" ]]; then
  echo "[probe] No section image found and fallback render failed." >&2
  exit 3
fi

echo "[probe] Using image: $IMG_PATH"

# 3) Build payload with base64 image (Python for portability)
export IMG_PATH MODEL CHUTES_API_BASE CHUTES_API_KEY
python - <<'PY'
import os, json, base64, sys
img_path = os.environ.get('IMG_PATH')
base = os.environ.get('CHUTES_API_BASE','').strip()
key  = os.environ.get('CHUTES_API_KEY','').strip()
model= os.environ.get('MODEL','').strip()
assert img_path and os.path.exists(img_path), f"No image at {img_path!r}"
assert base and key and model, "Missing CHUTES_API_BASE / CHUTES_API_KEY / MODEL"
with open(img_path,'rb') as f:
    b64 = base64.b64encode(f.read()).decode('ascii')
messages = [
  {"role":"system","content":"You are a precise vision assistant. Return only JSON; no code fences."},
  {"role":"user","content":[
    {"type":"text","text": 'Return only {"ok": true, "caption": string} as JSON.'},
    {"type":"image_url","image_url":{"url": f"data:image/png;base64,{b64}"}}
  ]}
]
payload = {
  "model": model,
  "messages": messages,
  "response_format": {"type":"json_object"},
  "max_tokens": 160,
  "temperature": 0
}
os.makedirs("scripts/artifacts", exist_ok=True)
with open("scripts/artifacts/chutes_vlm_probe.payload.json","w") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
PY

# 4) POST to OpenAI‑compatible endpoint with Bearer + x-api-key
RESP="$ART_DIR/chutes_vlm_probe.response.json"
HEAD="$ART_DIR/chutes_vlm_probe.headers.txt"
set +e
curl -sS \
  -D "$HEAD" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $CHUTES_API_KEY" \
  -H "x-api-key: $CHUTES_API_KEY" \
  -o "$RESP" \
  "$CHUTES_API_BASE/chat/completions" \
  --data @"$ART_DIR/chutes_vlm_probe.payload.json"
curl_ec=$?
set -e

# 5) Summarize + validate
python - <<'PY'
import json, re, sys
from pathlib import Path
head = Path('scripts/artifacts/chutes_vlm_probe.headers.txt').read_text('utf-8', errors='ignore')
resp_t = Path('scripts/artifacts/chutes_vlm_probe.response.json').read_text('utf-8', errors='ignore')
try:
    resp = json.loads(resp_t or '{}')
except Exception:
    print('[probe] Response is not JSON', file=sys.stderr)
    print(resp_t[:300])
    sys.exit(10)
m = re.search(r'^HTTP/\S+\s+(\d+)', head, re.M)
status = int(m.group(1)) if m else 0
content = (resp.get('choices') or [{}])[0].get('message',{}).get('content')
ok = False
caption = None
if isinstance(content, str):
    try:
        data = json.loads(content)
    except Exception:
        data = {}
elif isinstance(content, dict):
    data = content
else:
    data = {}
ok = bool(data.get('ok') is True)
caption = data.get('caption')
summary = {"http_status": status, "ok": ok, "has_caption": bool(caption), "caption_preview": (caption or '')[:120]}
Path('scripts/artifacts/chutes_vlm_probe.summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
exit_code = 0
if status != 200:
    exit_code = 20
elif not ok:
    exit_code = 21
elif not caption:
    exit_code = 22
sys.exit(exit_code)
PY

echo "[probe] Artifacts:"
echo " - $ART_DIR/chutes_vlm_probe.payload.json"
echo " - $ART_DIR/chutes_vlm_probe.headers.txt"
echo " - $ART_DIR/chutes_vlm_probe.response.json"
echo " - $ART_DIR/chutes_vlm_probe.summary.json"
