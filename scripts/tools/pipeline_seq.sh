#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Sequential pipeline runner with live logs to terminal and per-stage artifacts.
# Usage:
#   STAGE_TIMEOUT_SEC=600 scripts/tools/pipeline_seq.sh \
#     "data/input/pipeline/BHT_CV32A65X_with_requirements.pdf" \
#     data/results/pipeline_seq

PDF="${1:-}"
OUT_DIR="${2:-}"
if [[ -z "${PDF}" || -z "${OUT_DIR}" ]]; then
  echo "usage: $0 <PDF> <OUT_DIR>" >&2
  exit 2
fi
[[ -f "$PDF" ]] || { echo "error: PDF not found: $PDF" >&2; exit 3; }

STAGE_TIMEOUT_SEC=${STAGE_TIMEOUT_SEC:-600}

mkdir -p "$OUT_DIR"

run_stage() {
  local label="$1"; shift
  local -a cmd=("$@")
  local sdir="$OUT_DIR/seq_${label}"
  mkdir -p "$sdir"
  printf '%q ' "${cmd[@]}" >"$sdir/cmd.sh"; echo >>"$sdir/cmd.sh"; chmod +x "$sdir/cmd.sh"
  echo "[seq] === $label ===" | tee -a "$sdir/stage.out"
  echo "[seq] cmd: $sdir/cmd.sh" | tee -a "$sdir/stage.out"
  if timeout -k 10 "$STAGE_TIMEOUT_SEC" "${cmd[@]}" \
      2> >(tee "$sdir/stage.err" >&2) \
      | tee -a "$sdir/stage.out"; then
    echo "[seq] $label: OK" | tee -a "$sdir/stage.out"
    return 0
  else
    local ec=$?
    echo "[seq] $label: FAILED (exit $ec)" | tee -a "$sdir/stage.out"
    echo "[seq] tail -n 200 $sdir/stage.err" >&2
    tail -n 200 "$sdir/stage.err" || true
    return $ec
  fi
}

# Derive paths
pdf_base="$(basename "$PDF")"; pdf_stem="${pdf_base%.*}"
clean_pdf="$OUT_DIR/01_annotation_processor/${pdf_stem}_clean.pdf"

export PYTHONPATH="$(pwd)/src"

# Stage 01
run_stage 01_annotation_processor \
  python -m extractor.pipeline.steps.01_annotation_processor run "$PDF" -o "$OUT_DIR"

[[ -f "$clean_pdf" ]] || { echo "[seq] missing clean pdf: $clean_pdf" >&2; exit 1; }

# Stage 02 (inline to avoid IPC edge cases)
run_stage 02_marker_extractor \
  python -m extractor.pipeline.steps.02_marker_extractor run "$clean_pdf" -o "$OUT_DIR" --no-spawn

[[ -f "$OUT_DIR/02_marker_extractor/json_output/02_marker_blocks.json" ]] || { echo "[seq] missing 02_marker_blocks.json" >&2; exit 1; }

# Stage 04
run_stage 04_section_builder \
  python -m extractor.pipeline.steps.04_section_builder run \
    "$OUT_DIR/02_marker_extractor/json_output/02_marker_blocks.json" \
    --pdf-dir "$OUT_DIR/01_annotation_processor" -o "$OUT_DIR"

[[ -f "$OUT_DIR/04_section_builder/json_output/04_sections.json" ]] || { echo "[seq] missing 04_sections.json" >&2; exit 1; }

# Stage 05
run_stage 05_table_extractor \
  python -m extractor.pipeline.steps.05_table_extractor run \
    "$OUT_DIR/04_section_builder/json_output/04_sections.json" \
    --pdf-dir "$OUT_DIR/01_annotation_processor" -o "$OUT_DIR"

[[ -f "$OUT_DIR/05_table_extractor/json_output/05_tables.json" ]] || { echo "[seq] missing 05_tables.json" >&2; exit 1; }

# Stage 06 (skip descriptions; SciLLM-only code path)
run_stage 06_figure_extractor \
  python -m extractor.pipeline.steps.06_figure_extractor run \
    "$OUT_DIR/02_marker_extractor/json_output/02_marker_blocks.json" \
    --sections "$OUT_DIR/04_section_builder/json_output/04_sections.json" \
    --pdf-dir "$OUT_DIR/01_annotation_processor" -o "$OUT_DIR" --skip-descriptions --force-exit

[[ -f "$OUT_DIR/06_figure_extractor/json_output/06_figures.json" ]] || { echo "[seq] missing 06_figures.json" >&2; exit 1; }

# Stage 06b
run_stage 06b_layout_sketcher \
  python -m extractor.pipeline.steps.06b_layout_sketcher -o "$OUT_DIR"

# Stage 07 (text-only)
run_stage 07_reflow_section \
  python -m extractor.pipeline.steps.07_reflow_section run \
    --sections "$OUT_DIR/04_section_builder/json_output/04_sections.json" \
    --tables   "$OUT_DIR/05_table_extractor/json_output/05_tables.json" \
    --figures  "$OUT_DIR/06_figure_extractor/json_output/06_figures.json" \
    -o "$OUT_DIR" --no-include-images

[[ -f "$OUT_DIR/07_reflow_section/json_output/07_reflowed.json" ]] || { echo "[seq] missing 07_reflowed.json" >&2; exit 1; }

echo "[seq] DONE: $OUT_DIR"
