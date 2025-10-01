#!/usr/bin/env bash
set -euo pipefail

BASE_URL_DEFAULT="http://127.0.0.1:8080/main"
ATTEMPTS=${ATTEMPTS:-2}
DO_BUNDLE=1
for arg in "$@"; do
  case "$arg" in
    --no-bundle) DO_BUNDLE=0;;
    --bundle) DO_BUNDLE=1;;
  esac
done

ROOT=$(pwd)
ART_DIR="$ROOT/scripts/artifacts"
mkdir -p "$ART_DIR"

pushd prototypes/tabbed/html >/dev/null
echo "[typecheck] (180s)"; timeout 180s npm run -s typecheck
echo "[build] (420s)"; timeout 420s npm run -s build
LOG="$ART_DIR/preview_rinse_$(date +%s).log"
nohup npm run -s preview:8080 > "$LOG" 2>&1 &
PREVIEW_PID=$!
for i in $(seq 1 25); do curl -fsS -m 1 http://127.0.0.1:8080 >/dev/null && break || sleep 1; done
popd >/dev/null

BASE_URL=${BASE_URL:-$BASE_URL_DEFAULT}
RC=1
for i in $(seq 1 "$ATTEMPTS"); do
  echo "[ux:check attempt $i] BASE_URL=$BASE_URL"
  set +e
  timeout 120s npm run -s ux:check
  RC=$?
  set -e
  LATEST_LOG=$(ls -1t "$ART_DIR"/ux_check_*.log 2>/dev/null | head -n1 || true)
  LATEST_PNG=$(ls -1t "$ART_DIR"/ux_check_*.png 2>/dev/null | head -n1 || true)
  echo "attempt=$i rc=$RC log=$LATEST_LOG png=$LATEST_PNG"
  if [ "$RC" -eq 0 ]; then break; fi
done

kill $PREVIEW_PID 2>/dev/null || true; sleep 1; kill -9 $PREVIEW_PID 2>/dev/null || true

if [ "$RC" -eq 0 ]; then
  echo "[rinse-repeat] OK after $ATTEMPTS attempts (or fewer)."
  exit 0
fi

echo "[rinse-repeat] FAILED after $ATTEMPTS attempts."
if [ "$DO_BUNDLE" -ne 1 ]; then exit 2; fi

echo "[bundle] Building review bundle..."
python3 scripts/tools/copy_selected_files.py --root src/extractor/pipeline --output "$ART_DIR/extractor_pipeline_bundle.txt"
python3 scripts/tools/copy_selected_files.py --root prototypes/tabbed --output "$ART_DIR/tabbed_bundle.txt"
cat "$ART_DIR/extractor_pipeline_bundle.txt" "$ART_DIR/tabbed_bundle.txt" > "$ART_DIR/extractor_review_bundle.txt"

python3 - << 'PY'
import os, datetime, pathlib
ts = datetime.date.today().isoformat()
root = pathlib.Path.cwd()
text = pathlib.Path('REVIEW_BUNDLE_PROMPT.md').read_text(encoding='utf-8')
text = text.replace('<absolute path>', str(root)).replace('<YYYY‑MM‑DD>', ts)
out = [f"<!-- Auto-generated on {ts} -->", text, '===== BEGIN EXTRACTOR CODE BUNDLE =====']
out.append(pathlib.Path('scripts/artifacts/extractor_review_bundle.txt').read_text(encoding='utf-8'))
out.append('===== END EXTRACTOR CODE BUNDLE =====')
pathlib.Path('scripts/artifacts/EXTRACTOR_EXTERNAL_REVIEW.md').write_text('\n'.join(out), encoding='utf-8')
print('WROTE scripts/artifacts/EXTRACTOR_EXTERNAL_REVIEW.md')
PY

if command -v gh >/dev/null 2>&1 && gh auth status -h github.com >/dev/null 2>&1; then
  gh gist create -d "Extractor External Review (rinse-repeat) — $(date +%F)" \
    scripts/artifacts/EXTRACTOR_EXTERNAL_REVIEW.md | tee "$ART_DIR/EXTRACTOR_EXTERNAL_REVIEW.url"
else
  TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
  if [ -n "$TOKEN" ]; then
    python3 - << 'PY'
import json
content = open('scripts/artifacts/EXTRACTOR_EXTERNAL_REVIEW.md','r',encoding='utf-8').read()
payload = {'public': False, 'description': 'Extractor External Review (rinse-repeat)', 'files': {'EXTRACTOR_EXTERNAL_REVIEW.md': {'content': content}}}
open('scripts/artifacts/gist_payload.json','w',encoding='utf-8').write(json.dumps(payload))
PY
    RESP=$(curl -sS -H "Authorization: token $TOKEN" -H 'Accept: application/vnd.github.v3+json' \
      https://api.github.com/gists -d @scripts/artifacts/gist_payload.json || true)
    echo "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("html_url",""))' | tee "$ART_DIR/EXTRACTOR_EXTERNAL_REVIEW.url"
  else
    echo "Gist not created (missing gh auth or GITHUB_TOKEN)." | tee "$ART_DIR/EXTRACTOR_EXTERNAL_REVIEW.url"
  fi
fi

exit 2

