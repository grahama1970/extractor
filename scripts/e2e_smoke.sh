#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$ROOT"

# Start FastAPI server
( python -m extractor.core.scripts.server --host 127.0.0.1 --port 8000 >/tmp/fastapi.log 2>&1 & echo $! > /tmp/fastapi.pid )
# Wait for /docs or root
for i in $(seq 1 40); do
  if curl -sf http://127.0.0.1:8000/ >/dev/null; then break; fi
  sleep 0.25
done

# Start Vite preview on 5173
pushd prototypes/tabbed/html >/dev/null
npm install >/dev/null 2>&1 || true
( npm run -s preview -- --host 127.0.0.1 --port 5173 >/tmp/vite_preview.log 2>&1 & echo $! > /tmp/vite.pid )
popd >/dev/null
# Wait for /main
for i in $(seq 1 40); do
  if curl -sf http://127.0.0.1:5173/main >/dev/null; then break; fi
  sleep 0.25
done

# Ensure puppeteer installed at repo root
if [ ! -f package.json ]; then npm init -y >/dev/null 2>&1 || true; fi
npm i -D puppeteer >/dev/null 2>&1 || true

# Run smoke
node scripts/ux_smoke_ws.mjs

# Stage 14 offline smoke: generate a tiny debug-bundle and verify artifacts
TMP_BUNDLE=$(mktemp)
cat > "$TMP_BUNDLE" << 'JSON'
{
  "07_reflow_section": {
    "reflowed_sections": [
      {"title": "Intro", "level": 1, "reflow_status": "success", "reflowed": true, "text_chunks": [], "merged_tables": [], "ocr_corrections": {}}
    ]
  },
  "06_figure_extractor": {"figure_count": 0, "figures": []}
}
JSON

python -m extractor.pipeline.steps.14_report_generator debug-bundle "$TMP_BUNDLE" -o data/results/pipeline >/dev/null 2>&1 || true
test -f data/results/pipeline/final_report.json && echo "Stage 14: final_report.json OK" || echo "Stage 14: final_report.json MISSING"
test -f data/results/pipeline/final_report.md && echo "Stage 14: final_report.md OK" || echo "Stage 14: final_report.md MISSING"

# Teardown
kill $(cat /tmp/vite.pid) 2>/dev/null || true
kill $(cat /tmp/fastapi.pid) 2>/dev/null || true
