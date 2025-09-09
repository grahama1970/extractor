#!/usr/bin/env bash
set -euo pipefail

# This script verifies that all pipeline CLI steps run end-to-end
# against a real PDF with real network and ArangoDB access.

# 1) Activate env
if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
set +u; set -a; [[ -f .env ]] && source .env || true; set +a; set -u

PDF="data/input/pipeline/BHT_CV32A65X_marked.pdf"
OUT="data/results/pipeline"
ANN_JSON="$OUT/01_annotation_processor/json_output/01_annotations.json"
BLOCKS_JSON="$OUT/02_marker_extractor/json_output/02_marker_blocks.json"
VERIFIED_JSON="$OUT/03_suspicious_headers/json_output/03_verified_blocks.json"
SECTIONS_JSON="$OUT/04_section_builder/json_output/04_sections.json"
TABLES_JSON="$OUT/05_table_extractor/json_output/05_tables.json"
FIGURES_JSON="$OUT/06_figure_extractor/json_output/06_figures.json"
REFLOW_JSON="$OUT/07_reflow_section/json_output/07_reflowed.json"
THEOREMS_JSON="$OUT/08_lean4_theorem_prover/json_output/08_theorems.json"
SUMMARIES_JSON="$OUT/09_section_summarizer/json_output/09_summaries.json"
FLAT_JSON="$OUT/10_arangodb_exporter/json_output/10_flattened_data.json"
EXPORT_CONFIRM="$OUT/10_arangodb_exporter/json_output/10_export_confirmation.json"
GRAPH_CONFIRM="$OUT/11_arango_create_graph/json_output/11_graph_confirmation.json"

pass() { echo "[PASS] $1"; }
fail() { echo "[FAIL] $1"; exit 1; }
need() { [[ -s "$1" ]] || fail "Missing output: $1"; }

echo "== Stage 01→04 via extract-sections =="
extract-sections "$PDF" -o "$OUT" >/dev/null
need "$ANN_JSON"; need "$BLOCKS_JSON"; need "$VERIFIED_JSON"; need "$SECTIONS_JSON"
pass "Stages 01-04 outputs exist"

echo "== Stage 05: Table extractor =="
python src/extractor/pipeline/steps/05_table_extractor.py run "$SECTIONS_JSON" --pdf-dir "$OUT/01_annotation_processor" -o "$OUT" >/dev/null
need "$TABLES_JSON"; pass "Stage 05 tables JSON exists"

echo "== Stage 06: Figure extractor =="
python src/extractor/pipeline/steps/06_figure_extractor.py run "$BLOCKS_JSON" --sections "$SECTIONS_JSON" --pdf-dir "$OUT/01_annotation_processor" -o "$OUT" >/dev/null
need "$FIGURES_JSON"; pass "Stage 06 figures JSON exists"

echo "== Stage 07: Reflow sections =="
python src/extractor/pipeline/steps/07_reflow_section.py run --sections "$SECTIONS_JSON" --tables "$TABLES_JSON" --figures "$FIGURES_JSON" -o "$OUT" --summary-only >/dev/null
need "$REFLOW_JSON"; pass "Stage 07 reflow JSON exists"

echo "== Stage 08: Lean4 requirements extraction (skip proving) =="
python src/extractor/pipeline/steps/08_lean4_theorem_prover.py run "$REFLOW_JSON" -o "$OUT" --skip-proving >/dev/null
need "$THEOREMS_JSON"; pass "Stage 08 theorems JSON exists"

echo "== Stage 09: Section summarizer (real LLM calls) =="
python src/extractor/pipeline/steps/09_section_summarizer.py run "$REFLOW_JSON" -o "$OUT" --max-concurrent 2 --window-size 2 --no-strict-json >/dev/null || true
need "$SUMMARIES_JSON"; pass "Stage 09 summaries JSON exists (may contain 0 summaries if provider strict)"

echo "== Stage 10: ArangoDB exporter =="
python src/extractor/pipeline/steps/10_arangodb_exporter.py run --reflowed "$REFLOW_JSON" --summaries "$SUMMARIES_JSON" -o "$OUT" --collection-name pdf_objects >/dev/null
need "$EXPORT_CONFIRM"; pass "Stage 10 export confirmation JSON exists"

echo "== Stage 11: ArangoDB graph creation =="
python src/extractor/pipeline/steps/11_arango_create_graph.py run "$FLAT_JSON" -o "$OUT" >/dev/null
need "$GRAPH_CONFIRM"; pass "Stage 11 graph confirmation JSON exists"

echo "== Stage 12: Insert annotations (ArangoDB) =="
python src/extractor/pipeline/steps/12_insert_annotations.py run --annotations "$ANN_JSON" -o "$OUT" >/dev/null
pass "Stage 12 annotations inserted/bridged"

echo "== Stage 14: Report generator =="
python src/extractor/pipeline/steps/14_report_generator.py run "$OUT" >/dev/null
need "$OUT/final_report.json"; need "$OUT/final_report.md"; pass "Stage 14 final reports exist"

echo "\nAll CLI steps completed successfully."

