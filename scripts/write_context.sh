#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cat > "$ROOT/CONTEXT.md" <<'EOF'
# Context (regenerate via scripts/write_context.sh)

## Current state
- SciLLM/Chutes doctor passes (`uv run python scripts/tools/scillm_quick_doctor.py` with .env loaded).
- Accurate PDF pipeline completes Stages 01–10 with 09a enabled; 09b audit passes (errors=0).
- Flattened outputs remain 53 blocks; enforced parity formats (pdf/html/md/rst/docx/xml) ≥95% vs canonical.
- Local shim `src/scillm/` removed; scillm comes from editable `../litellm` (v1.77.3). Update via `scripts/update_scillm.sh`.
- Shutdown warning at exit (“Task was destroyed but it is pending!”) is benign; consider filing upstream.

## Key artifacts (latest accurate run)
- Run dir: `data/results/parity_runs/pdf`
- Reflow: `07_reflow_section/json_output/07_reflowed.json`
- Requirements: `07_requirements_miner/json_output/07_requirements.json` (1 requirement)
- Summaries: `09_section_summarizer/json_output/09_summaries.json`
- Annotator: `09a_pdf_annotator/annotated.pdf`, `annotations.json`, `legend.json`, previews
- Flattened: `10_arangodb_exporter/json_output/10_flattened_data.json` (53 blocks)

## Parity snapshot
- Enforced: pdf/html/md/rst/docx (simple default)/xml all ≥0.95 (html/md/rst/docx=1.000; xml≈0.962).
- Informational: pptx (54 blocks), xlsx (1 table, XLSX_SIMPLE_MODE=1), epub (226 blocks).
- Command: `make smoke-parity-gold` (enforces only the above; reports pptx/xlsx counts).

## CLI defaults
- Accurate mode runs 09a annotator by default.
- DOCX simple mode is default (parity-friendly); rich path via `DOCX_SIMPLE_MODE=0`.
- XLSX simple mode (`XLSX_SIMPLE_MODE=1`) is structure-first; parity not enforced.

## Update scillm
- Dependency is pinned to `scillm @ file:///home/graham/workspace/experiments/litellm`.
- Update with one command from repo root:
  ```bash
  scripts/update_scillm.sh
  ```

## Re-run doctor + pipeline
```bash
set -a && source .env && set +a
uv run python scripts/tools/scillm_quick_doctor.py

python -m src.cli data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
  data/results/parity_runs/pdf --mode accurate
```

## Open items
- File upstream issue for scillm shutdown warning if it persists.
- Verify 09_summaries content as needed.
- Keep scillm pinned (or update) via `scripts/update_scillm.sh` when notified.
EOF

echo "[write_context] Updated CONTEXT.md"
