#!/usr/bin/env bash
set -euo pipefail

# Simple, deterministic pipeline profile: text-first reflow, no images by default
# Stages: 01 -> 02 -> 04 -> 05 -> 06b -> 07 -> 14

PDF=${1:-"prototypes/tabbed/pdfs/BHT CV32A65X.pdf"}
OUT=${2:-"data/results/pipeline_simple"}

export PROFILE_SIMPLE=1
# Use offline predictors mode (no strict preflight on heavy models)
export OFFLINE_PDF_PREDICTORS=1
export PYTHONPATH=$(pwd)/src

echo "[simple] running to ${OUT} for ${PDF}"

python -m extractor.pipeline.steps.01_annotation_processor run "$PDF" -o "$OUT"
python -m extractor.pipeline.steps.02_marker_extractor run \
  "$OUT/01_annotation_processor/$(basename "${PDF%.*}")_clean.pdf" -o "$OUT" --no-spawn
python -m extractor.pipeline.steps.04_section_builder run \
  "$OUT/02_marker_extractor/json_output/02_marker_blocks.json" \
  --pdf-dir "$OUT/01_annotation_processor" -o "$OUT"
python -m extractor.pipeline.steps.05_table_extractor run \
  "$OUT/04_section_builder/json_output/04_sections.json" \
  --pdf-dir "$OUT/01_annotation_processor" -o "$OUT"
python -m extractor.pipeline.steps.06_figure_extractor run \
  "$OUT/02_marker_extractor/json_output/02_marker_blocks.json" \
  --sections "$OUT/04_section_builder/json_output/04_sections.json" \
  --pdf-dir "$OUT/01_annotation_processor" -o "$OUT" \
  --skip-descriptions
python -m extractor.pipeline.steps.06b_layout_sketcher -o "$OUT"
python -m extractor.pipeline.steps.07_reflow_section run \
  --sections "$OUT/04_section_builder/json_output/04_sections.json" \
  --tables   "$OUT/05_table_extractor/json_output/05_tables.json" \
  --figures  "$OUT/06_figure_extractor/json_output/06_figures.json" \
  -o "$OUT" --no-include-images
python -m extractor.pipeline.steps.14_report_generator run "$OUT"

echo "[simple] done -> $OUT"
