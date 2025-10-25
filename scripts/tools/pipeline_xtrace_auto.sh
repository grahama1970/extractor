#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Wrapper: accept <PDF> <OUT_DIR> and invoke the labeled xtrace runner.
# Usage:
#   scripts/tools/pipeline_xtrace_auto.sh "file.pdf" data/results/pipeline_xtrace

PDF="${1:-}"
OUT_DIR="${2:-}"

if [[ -z "${PDF}" || -z "${OUT_DIR}" ]]; then
  echo "usage: $0 <PDF> <OUT_DIR>" >&2
  exit 2
fi
if [[ ! -f "${PDF}" ]]; then
  echo "error: PDF not found: ${PDF}" >&2
  exit 3
fi

mkdir -p "${OUT_DIR}"

# Derive cleaned PDF path produced by Stage 01
pdf_base="$(basename "${PDF}")"
pdf_stem="${pdf_base%.*}"
clean_pdf="${OUT_DIR%/}/01_annotation_processor/${pdf_stem}_clean.pdf"

# Convenience env (not required):
export PYTHONPATH="$(pwd)/src"

# Option: force Stage 02 inline to rule out subprocess/IPC edge cases
S2_NO_SPAWN=${XTRACE_S2_NO_SPAWN:-1}
if [[ "${S2_NO_SPAWN}" == "1" ]]; then
  echo "[auto] Stage 02 will run with --no-spawn"
  S2_ARGS=("--no-spawn")
else
  S2_ARGS=()
fi

# Compose labeled stages for the array-safe xtrace runner
scripts/tools/pipeline_xtrace.sh \
  "${OUT_DIR}" \
  "01_annotation_processor" python -m extractor.pipeline.steps.01_annotation_processor run "${PDF}" -o "${OUT_DIR}" :: \
  "02_marker_extractor" python -m extractor.pipeline.steps.02_marker_extractor run "${clean_pdf}" -o "${OUT_DIR}" "${S2_ARGS[@]}" :: \
  "04_section_builder" python -m extractor.pipeline.steps.04_section_builder run \
      "${OUT_DIR%/}/02_marker_extractor/json_output/02_marker_blocks.json" \
      --pdf-dir "${OUT_DIR%/}/01_annotation_processor" -o "${OUT_DIR}" :: \
  "05_table_extractor" python -m extractor.pipeline.steps.05_table_extractor run \
      "${OUT_DIR%/}/04_section_builder/json_output/04_sections.json" \
      --pdf-dir "${OUT_DIR%/}/01_annotation_processor" -o "${OUT_DIR}" :: \
  "06_figure_extractor" python -m extractor.pipeline.steps.06_figure_extractor run \
      "${OUT_DIR%/}/02_marker_extractor/json_output/02_marker_blocks.json" \
      --sections "${OUT_DIR%/}/04_section_builder/json_output/04_sections.json" \
      --pdf-dir "${OUT_DIR%/}/01_annotation_processor" -o "${OUT_DIR}" --skip-descriptions --force-exit :: \
  "06b_layout_sketcher" python -m extractor.pipeline.steps.06b_layout_sketcher -o "${OUT_DIR}" :: \
  "07_reflow_section" python -m extractor.pipeline.steps.07_reflow_section run \
      --sections "${OUT_DIR%/}/04_section_builder/json_output/04_sections.json" \
      --tables   "${OUT_DIR%/}/05_table_extractor/json_output/05_tables.json" \
      --figures  "${OUT_DIR%/}/06_figure_extractor/json_output/06_figures.json" \
      -o "${OUT_DIR}" --no-include-images

echo "[auto] summary: ${OUT_DIR%/}/xtrace_*/summary.json (latest run)"
