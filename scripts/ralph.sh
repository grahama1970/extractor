#!/bin/bash
# ralph.sh — The Ralph Wiggum Orchestrator
# ALIGNED to run_pipeline.py (Production Sequence)

set -e
set -o pipefail

# Configuration
PIPELINE_DIR="data/results/pipeline_ralph_aligned"
# Default input matches GOAL.md
INPUT_PDF="${1:-data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf}"
PYTHON="python -m"

# Ensure input exists
if [ ! -f "$INPUT_PDF" ]; then
    echo "Error: Input PDF not found at $INPUT_PDF"
    # Fallback to known location if distinct
    if [ -f "data/pdfs/BHT CV32A65X.pdf" ]; then
        echo "Falling back to data/pdfs/BHT CV32A65X.pdf"
        INPUT_PDF="data/pdfs/BHT CV32A65X.pdf"
    else
        exit 1
    fi
fi

mkdir -p "$PIPELINE_DIR"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[Ralph]${NC} $1"
}

error() {
    echo -e "${RED}[Ralph] ERROR:${NC} $1"
    exit 1
}

# --- 1. S01: Annotations ---
log "Running Stage 01: Annotation Processor on $INPUT_PDF..."
$PYTHON extractor.pipeline.steps.s01_annotation_processor --pipeline-dir "$PIPELINE_DIR" --pdf "$INPUT_PDF"
$PYTHON extractor.pipeline.steps.s01_annotation_processor --pipeline-dir "$PIPELINE_DIR" --verify-only || error "S01 Failed Verification"

# --- 2. S02: Marker ---
log "Running Stage 02: PDF Marker..."
$PYTHON extractor.pipeline.steps.s02_marker_extractor --pipeline-dir "$PIPELINE_DIR"
$PYTHON extractor.pipeline.steps.s02_marker_extractor --pipeline-dir "$PIPELINE_DIR" --verify-only || error "S02 Failed Verification"

# --- 3. S03: Suspicious Headers (Loop) ---
log "Running Stage 03: Suspicious Headers..."
$PYTHON extractor.pipeline.steps.s03_suspicious_headers --pipeline-dir "$PIPELINE_DIR"
$PYTHON extractor.pipeline.steps.s03_suspicious_headers --pipeline-dir "$PIPELINE_DIR" --verify-only || error "S03 Failed Verification"

# --- 4. S04: Section Builder ---
log "Running Stage 04: Section Builder..."
$PYTHON extractor.pipeline.steps.s04_section_builder --pipeline-dir "$PIPELINE_DIR"
$PYTHON extractor.pipeline.steps.s04_section_builder --pipeline-dir "$PIPELINE_DIR" --verify-only || error "S04 Failed Verification"

# --- 4a. S04a: Layout Audit (New) ---
log "Running Stage 04a: Layout Audit..."
$PYTHON extractor.pipeline.steps.s04a_layout_audit --pipeline-dir "$PIPELINE_DIR"
# No verify-only yet

# --- 5. S05: Tables ---
log "Running Stage 05: Table Extractor..."
$PYTHON extractor.pipeline.steps.s05_table_extractor --pipeline-dir "$PIPELINE_DIR"
$PYTHON extractor.pipeline.steps.s05_table_extractor --pipeline-dir "$PIPELINE_DIR" --verify-only || error "S05 Failed Verification"

# --- 5b. S05b: Table Descriptions (New) ---
log "Running Stage 05b: Table Describer..."
$PYTHON extractor.pipeline.steps.s05b_table_describer --pipeline-dir "$PIPELINE_DIR"
$PYTHON extractor.pipeline.steps.s05b_table_describer --pipeline-dir "$PIPELINE_DIR" --verify-only || error "S05b Failed Verification"

# --- 5c. S05c: Table Merger (New) ---
log "Running Stage 05c: Table Merger..."
$PYTHON extractor.pipeline.steps.s05c_table_merger --pipeline-dir "$PIPELINE_DIR"
$PYTHON extractor.pipeline.steps.s05c_table_merger --pipeline-dir "$PIPELINE_DIR" --verify-only || error "S05c Failed Verification"

# --- 6. S06: Figures ---
log "Running Stage 06: Figure Extractor..."
$PYTHON extractor.pipeline.steps.s06_figure_extractor --pipeline-dir "$PIPELINE_DIR" --pdf-dir "$PIPELINE_DIR/01_annotation_processor"
$PYTHON extractor.pipeline.steps.s06_figure_extractor --pipeline-dir "$PIPELINE_DIR" --verify-only || error "S06 Failed Verification"

# --- 6b. S06b: Figure Describer (New) ---
log "Running Stage 06b: Figure Describer..."
$PYTHON extractor.pipeline.steps.s06b_figure_describer --pipeline-dir "$PIPELINE_DIR"
$PYTHON extractor.pipeline.steps.s06b_figure_describer --pipeline-dir "$PIPELINE_DIR" --verify-only || error "S06b Failed Verification"

# --- 7. S07: DuckDB Ingest (New) ---
log "Running Stage 07: DuckDB Ingest..."
$PYTHON extractor.pipeline.steps.s07_duckdb_ingest --pipeline-dir "$PIPELINE_DIR"
# Implicitly verified by S08/S10

# --- 8. S08: Requirements ---
log "Running Stage 08: Requirements Extraction..."
$PYTHON extractor.pipeline.steps.s08_extract_requirements --pipeline-dir "$PIPELINE_DIR"

# --- 9. S09: Summaries ---
log "Running Stage 09: Section Summarizer..."
$PYTHON extractor.pipeline.steps.s09_section_summarizer --pipeline-dir "$PIPELINE_DIR"
$PYTHON extractor.pipeline.steps.s09_section_summarizer --pipeline-dir "$PIPELINE_DIR" --verify-only || error "S09 Failed Verification"

# --- 10. S10: Export ---
log "Running Stage 10: Markdown Exporter..."
$PYTHON extractor.pipeline.steps.s10_markdown_exporter --pipeline-dir "$PIPELINE_DIR"
$PYTHON extractor.pipeline.steps.s10_markdown_exporter --pipeline-dir "$PIPELINE_DIR" --verify-only || error "S10 Failed Verification"

# --- 14. S14: Report (New) ---
log "Running Stage 14: Report Generator..."
$PYTHON extractor.pipeline.steps.s14_report_generator --pipeline-dir "$PIPELINE_DIR"

log "✅ Ralph Pipeline Complete (Fully Aligned)!"
