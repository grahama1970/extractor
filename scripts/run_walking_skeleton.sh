#!/usr/bin/env bash
set -euo pipefail

PDF_PATH=${1:-prototypes/tabbed/pdfs/BHT\ CV32A65X.pdf}
OUT_DIR=${2:-data/results/pipeline}

bash scripts/preflight_pipeline.sh

echo "== Walking skeleton on: $PDF_PATH =="

# 01/02/03/04/05/06/06c/07/10/14 minimal flow
python src/extractor/pipeline/steps/01_annotation_processor.py run "$PDF_PATH" -o "$OUT_DIR"
python src/extractor/pipeline/steps/02_marker_extractor.py run "$PDF_PATH" -o "$OUT_DIR" --no-spawn --timeout 1200
python src/extractor/pipeline/steps/03_suspicious_headers.py run "$OUT_DIR/02_marker_extractor/json_output/02_marker_blocks.json" -o "$OUT_DIR" --skip-llm
python src/extractor/pipeline/steps/04_section_builder.py run "$OUT_DIR/03_suspicious_headers/json_output/03_verified_blocks.json" --pdf-dir "$OUT_DIR/01_annotation_processor" -o "$OUT_DIR"
python src/extractor/pipeline/steps/05_table_extractor.py run "$OUT_DIR/04_section_builder/json_output/04_sections.json" --pdf-dir "$OUT_DIR/01_annotation_processor" -o "$OUT_DIR"

# Figures: safe caps; set FIGURE_MAX_PER_DOC to keep small
FIGURE_MAX_PER_DOC=${FIGURE_MAX_PER_DOC:-12}
FIGURE_DESC=${FIGURE_DESC:-0}
DESC_FLAG="--skip-descriptions"
case "${FIGURE_DESC,,}" in
  1|true|yes) DESC_FLAG="";;
 esac
python src/extractor/pipeline/steps/06_figure_extractor.py run \
  "$OUT_DIR/02_marker_extractor/json_output/02_marker_blocks.json" \
  --sections "$OUT_DIR/04_section_builder/json_output/04_sections.json" \
  --pdf-dir "$OUT_DIR/01_annotation_processor" \
  -o "$OUT_DIR" \
  ${DESC_FLAG}

BASE_NAME=$(basename "$PDF_PATH")
CLEAN_NAME="${BASE_NAME%.pdf}_clean.pdf"
python src/extractor/pipeline/steps/06c_pdf_annotator.py \
  "$OUT_DIR/01_annotation_processor/$CLEAN_NAME" \
  --sections "$OUT_DIR/04_section_builder/json_output/04_sections.json" \
  --tables "$OUT_DIR/05_table_extractor/json_output/05_tables.json" \
  --figures "$OUT_DIR/06_figure_extractor/json_output/06_figures.json" \
  -o "$OUT_DIR"

# Stage 07: summary-only (no LLM); deterministic pass-through of merged text
STAGE07_INCLUDE_FIGURES=0 STAGE07_ATTACH_SECTION_IMAGE=0 \
python src/extractor/pipeline/steps/07_reflow_section.py run \
  --sections "$OUT_DIR/04_section_builder/json_output/04_sections.json" \
  --tables "$OUT_DIR/05_table_extractor/json_output/05_tables.json" \
  --figures "$OUT_DIR/06_figure_extractor/json_output/06_figures.json" \
  --summary-only --allow-fallback \
  -o "$OUT_DIR"

# Minimal summaries (no LLM) for Stage 10
SUM_PATH=$(python scripts/make_min_summaries.py "$OUT_DIR/04_section_builder/json_output/04_sections.json" "$OUT_DIR")

python src/extractor/pipeline/steps/10_arangodb_exporter.py run \
  --reflowed "$OUT_DIR/07_reflow_section/json_output/07_reflowed.json" \
  --summaries "$SUM_PATH" \
  --skip-embeddings --fast-embeddings \
  -o "$OUT_DIR"

python src/extractor/pipeline/steps/14_report_generator.py run "$OUT_DIR"

echo "== Walking skeleton completed: $OUT_DIR =="
