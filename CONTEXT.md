# Restart Context — Chrome DevTools MCP + Stage 05 QA Loop

Generated: 2025-10-02
Location: /home/graham/workspace/experiments/extractor

This note captures exactly where we left off so you can restart the Codex CLI,
let the chrome-devtools MCP server relaunch in headless mode, and pick up the
verification loop without losing state.

---

## 1. One-Time Local Prep

1. Ensure a headless Chrome is running on port 9222:
   ```bash
   source ~/.zshrc && ch-headless
   # or
   /usr/bin/google-chrome \
     --headless --disable-gpu \
     --remote-debugging-port=9222 \
     --user-data-dir=/tmp/chromium-mcp \
     --disable-sync --disable-breakpad \
     --no-sandbox --disable-dev-shm-usage --no-first-run \
     >/tmp/chromium-mcp.log 2>&1 &
   ```
   - Check: `curl -fsS http://127.0.0.1:9222/json/version | jq`
   - Browser log: `/tmp/chromium-mcp.log`

2. Restart the Codex CLI (or its chrome-devtools MCP task) so it uses the
   updated config:
   - `~/.codex/config.toml` now sets
     `args = ["chrome-devtools-mcp@latest", "--headless", "--isolated", "--logFile", "/tmp/cdmcp.log"]`
   - MCP log: `/tmp/cdmcp.log`

---

## 2. Post-Restart Verification

Run these once Codex is back:

1. **MCP sanity** – in the CLI:
   ```
   chrome-devtools__list_pages
   ```
   Expect a list of targets instead of “Target closed”.

2. **UX health gate for `/main`** (requires Vite dev server on 8080 and backend
   on 8001):
   ```bash
   BROWSERLESS_DISCOVERY_URL=http://127.0.0.1:9222/json/version \
   BASE_URL=http://127.0.0.1:8080/main \
   node scripts/ux_check_cdp_auto.mjs
   ```
   - Artifacts land under `scripts/artifacts/ux_check_cdp_*.{png,log}`
   - Pass criteria: no dev overlay, no console/page errors, no failed
     document/script/stylesheet requests, `#root` mounted.
   - If console shows 500s for `/api/pipeline/pdf-status`, start the FastAPI
     backend (`python -m extractor.core.scripts.server --host 0.0.0.0 --port 8001`) or
     guard the fetch in the frontend.

3. **Optional network capture** (for any failing requests):
   ```bash
   BROWSERLESS_DISCOVERY_URL=http://127.0.0.1:9222/json/version \
   BASE_URL=http://127.0.0.1:8080/main \
   node scripts/diagnostics/cdp_network_capture.mjs
   ```
   Produces `scripts/artifacts/cdp_network_main_*.ndjson` for quick triage.

---

## 3. Stage 05 QA on Large PDFs (Existing Outputs)

Pipeline runs are stored under `data/results/pipeline_runs/`:
- `design_doc/` → Design Documentation for CV32A65X architecture.pdf
- `nvidia_ampere/` → nvidia-ampere-architecture-whitepaper.pdf
- `astro_2507/` → 2507.00114v1_astrophysics.pdf

Each directory contains Stage 01→05 outputs with the clean PDF copied to
`tmp_pdf/` for deterministic provenance.

Metrics summaries (Stage 05 quality-aware fallback) live in:
- `scripts/artifacts/stage05_metrics_design_doc.json`
- `scripts/artifacts/stage05_metrics_nvidia_ampere.json`
- `scripts/artifacts/stage05_metrics_astro_2507.json`

Annotated PDFs & PNGs (fallback pages only):
- `scripts/artifacts/annotated_design_doc.pdf` (+ `_pages/`)
- `scripts/artifacts/annotated_nvidia_ampere.pdf` (+ `_pages/`)
- `scripts/artifacts/annotated_astro_2507.pdf` (+ `_pages/`)

To regenerate for any PDF:
```bash
# Example for a new document
slug=my_pdf_slug
PDF=data/pdfs/<file>.pdf
OUT=data/results/pipeline_runs/$slug
rm -rf "$OUT" && mkdir -p "$OUT/tmp_pdf"
python src/extractor/pipeline/steps/01_annotation_processor.py run "$PDF" -o "$OUT"
CLEAN=$(jq -r .clean_pdf_path "$OUT/01_annotation_processor/json_output/01_annotations.json")
cp "$CLEAN" "$OUT/tmp_pdf/"
python src/extractor/pipeline/steps/02_marker_extractor.py run "$OUT/tmp_pdf/$(basename "$CLEAN")" -o "$OUT" --no-spawn
python src/extractor/pipeline/steps/03_suspicious_headers.py run "$OUT/02_marker_extractor/json_output/02_marker_blocks.json" --pdf-dir "$OUT/tmp_pdf" -o "$OUT" --skip-llm
python src/extractor/pipeline/steps/04_section_builder.py run "$OUT/03_suspicious_headers/json_output/03_verified_blocks.json" --pdf-dir "$OUT/tmp_pdf" -o "$OUT"
python src/extractor/pipeline/steps/05_table_extractor.py run "$OUT/04_section_builder/json_output/04_sections.json" --pdf-dir "$OUT/tmp_pdf" -o "$OUT"
uv run scripts/tools/pdf_annotate_from_pipeline.py \
  --input-pdf "$OUT/01_annotation_processor/$(basename "$CLEAN")" \
  --results "$OUT" \
  --output scripts/artifacts/annotated_${slug}.pdf \
  --fallback-only --export-pages
```

---

## 4. Outstanding Tasks

- Bring the backend online (or guard the fetch) so `/api/pipeline/pdf-status`
  no longer returns 500s, then rerun the `/main` gate and save clean artifacts.
- Migrate remaining `tests/smoke/**` suites into `scenarios/` and leave
  `tests/` for deterministic unit/integration tests.
- Use the updated annotator when tweaking Stage 05 thresholds; fallback tables
  are highlighted red and labelled with `frag=`, `s=`, and `fallback` markers.

---

Once the CLI restarts, follow the checklist above and we can continue the loop
without losing context.
