#!/usr/bin/env bash
set -euo pipefail

PDF_PATH=${1:-prototypes/tabbed/pdfs/BHT\ CV32A65X.pdf}
OUT_DIR=${2:-data/results/pipeline}

bash scripts/preflight_pipeline.sh

echo "== Walking skeleton on: $PDF_PATH =="

# 01/02/03/04/05/06/06c/07/10/14 minimal flow
python src/extractor/pipeline/steps/01_annotation_processor.py run "$PDF_PATH" -o "$OUT_DIR"
python src/extractor/pipeline/steps/02_marker_extractor.py run "$PDF_PATH" -o "$OUT_DIR"
python src/extractor/pipeline/steps/03_suspicious_headers.py run "$OUT_DIR/02_marker_extractor/json_output/02_marker_blocks.json" -o "$OUT_DIR"
python src/extractor/pipeline/steps/04_section_builder.py run "$OUT_DIR/03_suspicious_headers/json_output/03_verified_blocks.json" --pdf-dir "$OUT_DIR/01_annotation_processor" -o "$OUT_DIR"
python src/extractor/pipeline/steps/05_table_extractor.py run "$OUT_DIR/04_section_builder/json_output/04_sections.json" --pdf-dir "$OUT_DIR/01_annotation_processor" -o "$OUT_DIR"

# Figures: safe caps; set FIGURE_MAX_PER_DOC to keep small
FIGURE_MAX_PER_DOC=${FIGURE_MAX_PER_DOC:-12} \
python src/extractor/pipeline/steps/06_figure_extractor.py run \
  "$OUT_DIR/02_marker_extractor/json_output/02_marker_blocks.json" \
  --sections "$OUT_DIR/04_section_builder/json_output/04_sections.json" \
  --pdf-dir "$OUT_DIR/01_annotation_processor" \
  -o "$OUT_DIR"

python src/extractor/pipeline/steps/06c_pdf_annotator.py run \
  "$OUT_DIR/01_annotation_processor/*_clean.pdf" \
  --sections "$OUT_DIR/04_section_builder/json_output/04_sections.json" \
  --tables "$OUT_DIR/05_table_extractor/json_output/05_tables.json" \
  --figures "$OUT_DIR/06_figure_extractor/json_output/06_figures.json" \
  -o "$OUT_DIR"

# Stage 07: rely on existing JSON strict path; disable figures/section image to keep deterministic
STAGE07_INCLUDE_FIGURES=0 STAGE07_ATTACH_SECTION_IMAGE=0 \
python src/extractor/pipeline/steps/07_reflow_section.py run \
  --sections "$OUT_DIR/04_section_builder/json_output/04_sections.json" \
  --tables "$OUT_DIR/05_table_extractor/json_output/05_tables.json" \
  --figures "$OUT_DIR/06_figure_extractor/json_output/06_figures.json" \
  -o "$OUT_DIR"

python src/extractor/pipeline/steps/10_arangodb_exporter.py run \
  --reflowed "$OUT_DIR/07_reflow_section/json_output/07_reflowed.json" \
  -o "$OUT_DIR"

python src/extractor/pipeline/steps/14_report_generator.py run "$OUT_DIR"

echo "== Walking skeleton completed: $OUT_DIR =="

