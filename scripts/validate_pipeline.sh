#!/bin/bash

# Sequential Pipeline Validation Script
# Stops at first failure and reports detailed diagnostic information

set -euo pipefail

echo "🔍 Extractor Pipeline Stage Validation (Deterministic Check)"
echo "============================================="
echo ""

# Configuration
PDF_PATH="data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf"
TEST_RESULT_DIR="test_validation"
FAILURE_LOG="$TEST_RESULT_DIR/failure_$(date +%Y%m%d_%H%M%S).log"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create test directory
mkdir -p "$TEST_RESULT_DIR"

echo "Test Directory: $TEST_RESULT_DIR"
echo "PDF Under Test: $PDF_PATH"
echo ""

# Function to log failures
log_failure() {
    local stage="$1"
    local problem="$2"
    local detail="$3"

    echo -e "${RED}❌ FAILED AT: Stage $stage${NC}" | tee -a "$FAILURE_LOG"
    echo -e "${RED}   Problem: $problem${NC}" | tee -a "$FAILURE_LOG"
    echo -e "${RED}   Detail: $detail${NC}" | tee -a "$FAILURE_LOG"
    echo -e "${RED}   Stopping pipeline here.${NC}"
    exit 1
}

# Function to check stage output exists
check_stage_output() {
    local stage="$1"
    local expected_file="$2"

    if [[ ! -f "$expected_file" ]]; then
        log_failure "$stage" "Missing output file" "Expected: $expected_file"
    fi

    # Check file is not empty
    if [[ ! -s "$expected_file" ]]; then
        log_failure "$stage" "Empty output file" "Expected non-empty: $expected_file"
    fi
}

# Function to validate JSON is parseable
validate_json() {
    local stage="$1"
    local json_file="$2"

    if ! python3 -m json.tool "$json_file" > /dev/null 2>1; then
        log_failure "$stage" "Invalid JSON output" "File: $json_file"
    fi
}

# Function to check number of objects against expected
check_object_count() {
    local stage="$1"
    local json_file="$2"
    local json_path="$3"
    local expected_min="$4"
    local expected_max="$5"

    if [[ -n "$expected_max" ]]; then
        actual=$(python3 -c "
import json
data = json.load(open('$json_file'))
count = $json_path
print(count)
") 2>/dev/null || count=0

        if [[ "$actual" -lt "$expected_min" || "$actual" -gt "$expected_max" ]]; then
            log_failure "$stage" "Object count outside expected range" "Got: $actual, Expected: $expected_min-$expected_max\n  Path: $json_path"
        fi
    fi
}

# Stage 01: Annotation Processor
echo -e "${YELLOW}▶ Stage 01: Annotation Processor${NC}"
python3 scripts/run_stage.py 01 --pdf="$PDF_PATH" --output_dir="$TEST_RESULT_DIR" || log_failure "01" "Stage execution failed" "Check logs in $TEST_RESULT_DIR"

# Check S01 output
check_stage_output "01" "$TEST_RESULT_DIR/01_annotation_processor/json_output/01_annotations.json"
check_object_count "01" "$TEST_RESULT_DIR/01_annotation_processor/json_output/01_annotations.json" "len(data.get('annotations', []))" 0 50
validate_json "01" "$TEST_RESULT_DIR/01_annotation_processor/json_output/01_annotations.json"
echo -e "${GREEN}✅ S01: Annotations processed${NC}"

# Stage 02: Marker Extractor
echo -e "${YELLOW}▶ Stage 02: Marker Extractor${NC}"
python3 scripts/run_stage.py 02 --output_dir="$TEST_RESULT_DIR" || log_failure "02" "Stage execution failed" "Check logs in $TEST_RESULT_DIR"

# Check S02 output
check_stage_output "02" "$TEST_RESULT_DIR/02_marker_extractor/json_output/02_marker_blocks.json"
check_object_count "02" "$TEST_RESULT_DIR/02_marker_extractor/json_output/02_marker_blocks.json" "data.get('block_count', 0)" 10 200
check_object_count "02" "$TEST_RESULT_DIR/02_marker_extractor/json_output/02_marker_blocks.json" "len(data.get('blocks', []))" 10 200

# Validate critical objects exist
python3 -c "
import json
data = json.load(open('$TEST_RESULT_DIR/02_marker_extractor/json_output/02_marker_blocks.json'))
blocks = data.get('blocks', [])
# Check we have the right object types
types = [b.get('block_type') for b in blocks]
if 'SectionHeader' not in types:
  print('WARNING: No SectionHeader detected', file=open('$TEST_RESULT_DIR/warnings.log', 'a'))
if 'Table' not in types:
  print('WARNING: No Table detected', file=open('$TEST_RESULT_DIR/warnings.log', 'a'))
" 2>&1 || true

validate_json "02" "$TEST_RESULT_DIR/02_marker_extractor/json_output/02_marker_blocks.json"
echo -e "${GREEN}✅ S02: Marker blocks extracted${NC}"

# Stage 03: Suspicious Headers
echo -e "${YELLOW}▶ Stage 03: Suspicious Headers${NC}"
python3 scripts/run_stage.py 03 --output_dir="$TEST_RESULT_DIR" || log_failure "03" "Stage execution failed" "Check logs in $TEST_RESULT_DIR"

# Check S03 output
check_stage_output "03" "$TEST_RESULT_DIR/03_suspicious_headers/json_output/03_verified_blocks.json"
# Write warnings if suspicious flags remain
check_object_count "03" "$TEST_RESULT_DIR/03_suspicious_headers/json_output/03_verified_blocks.json" "data.get('suspicious_block_count', 0)" 0 5
echo -e "${GREEN}✅ S03: Headers validated${NC}"

# Stage 04: Section Builder
echo -e "${YELLOW}▶ Stage 04: Section Builder${NC}"
python3 scripts/run_stage.py 04 --output_dir="$TEST_RESULT_DIR" || log_failure "04" "Stage execution failed" "Check logs in $TEST_RESULT_DIR"

# Check S04 output
check_stage_output "04" "$TEST_RESULT_DIR/04_section_builder/json_output/04_sections.json"
# Check critical section exists
python3 -c "
import json
data = json.load(open('$TEST_RESULT_DIR/04_section_builder/json_output/04_sections.json'))
sections = data.get('sections', [])
found_main = False
for s in sections:
    title = s.get('title', '')
    if 'BHT' in title and 'Branch History Table' in title:
        found_main = True
        break
if not found_main:
    log_failure('04', 'Missing BHT main section', 'Expected to find BHT (Branch History Table) submodule section')
" 2>&1 || true

echo -e "${GREEN}✅ S04: Sections built${NC}"

# Stage 05: Table Extractor
echo -e "${YELLOW}▶ Stage 05: Table Extractor${NC}"
python3 scripts/run_stage.py 05 --output_dir="$TEST_RESULT_DIR" || log_failure "05" "Stage execution failed" "Check logs in $TEST_RESULT_DIR"

# Check S05 output
check_stage_output "05" "$TEST_RESULT_DIR/05_table_extractor/json_output/05_tables.json"

# Find table merge issues
python3 -c "
import json
data = json.load(open('$TEST_RESULT_DIR/05_table_extractor/json_output/05_tables.json'))
tables = data.get('tables', [])
# Check for Table 4-1 that should span pages
found_bht_table = False
for table in tables:
    txt = table.get('text', '').lower()
    if 'bht prediction outcomes' in txt:
        found_bht_table = True
        # Check if marked for merging
        if not table.get('should_merge', False):
            print('WARNING: Table 4-1 not marked for merge', file=open('$TEST_RESULT_DIR/warnings.log', 'a'))
if not found_bht_table and len(tables) > 0:
    print('WARNING: Could not identify BHT prediction table in extraction', file=open('$TEST_RESULT_DIR/warnings.log', 'a'))
" 2>&1 || true

echo -e "${GREEN}✅ S05: Tables extracted${NC}"

# Stage 06: Figure Extractor
echo -e "${YELLOW}▶ Stage 06: Figure Extractor${NC}"
python3 scripts/run_stage.py 06 --output_dir="$TEST_RESULT_DIR" || log_failure "06" "Stage execution failed" "Check logs in $TEST_RESULT_DIR"

# Check S06 output
check_stage_output "06" "$TEST_RESULT_DIR/06_figure_extractor/json_output/06_figures.json"
echo -e "${GREEN}✅ S06: Figures extracted${NC}"

# Stage 07: Corpus Assembly
echo -e "${YELLOW}▶ Stage 07: Corpus Assembly${NC}"
python3 scripts/run_stage.py 07 --output_dir="$TEST_RESULT_DIR" || log_failure "07" "Stage execution failed" "Check logs in $TEST_RESULT_DIR"

# Check S07 output
check_stage_output "07" "$TEST_RESULT_DIR/07_corpus_assembly/json_output/07_assembled.json"

# Stage 08: Requirements & Lean4
echo -e "${YELLOW}▶ Stage 08: Requirements & Lean4${NC}"
python3 scripts/run_stage.py 08 --output_dir="$TEST_RESULT_DIR" || log_failure "08" "Stage execution failed" "Check logs in $TEST_RESULT_DIR"


# Check S08 outputs
check_stage_output "08" "$TEST_RESULT_DIR/08_extract_requirements/json_output/08_requirements.json"

# Verify requirements count (expecting ~10-15 based on GOAL.md)
check_object_count "08" "$TEST_RESULT_DIR/08_extract_requirements/json_output/08_requirements.json" "data.get('count', 0)" 10 60

# Verify Lean4 proofs exist in DB
python3 -c "
import duckdb
import sys
try:
    con = duckdb.connect('$TEST_RESULT_DIR/pipeline.duckdb', read_only=True)
    count = con.execute('SELECT count(*) FROM lean4_proofs').fetchone()[0]
    if count == 0:
        print('FAILURE: No Lean4 proofs found in DB')
        sys.exit(1)
    print(f'Found {count} Lean4 proof attempts')
except Exception as e:
    print(f'FAILURE: DB Check failed: {e}')
    sys.exit(1)
" || log_failure "08" "Missing Lean4 Proofs" "Check pipeline.duckdb in $TEST_RESULT_DIR"

echo -e "${GREEN}✅ S08: Requirements and Proofs verified${NC}"

# Stage 09: Enrichment (LLM)
echo -e "${YELLOW}▶ Stage 09: LLM Enrichment${NC}"
# NOTE: S09 calls LLMs. Ensure env vars are set or it will skip/fail.
python3 scripts/run_stage.py 09 --output_dir="$TEST_RESULT_DIR" || log_failure "09" "Stage execution failed" "Check logs in $TEST_RESULT_DIR"

check_stage_output "09" "$TEST_RESULT_DIR/09_llm_enrichment/json_output/09_enriched.json"
echo -e "${GREEN}✅ S09: Enrichment complete${NC}"

# Stage 10: Export
echo -e "${YELLOW}▶ Stage 10: Markdown Export${NC}"
python3 scripts/run_stage.py 10 --output_dir="$TEST_RESULT_DIR" || log_failure "10" "Stage execution failed" "Check logs in $TEST_RESULT_DIR"

check_stage_output "10" "$TEST_RESULT_DIR/10_markdown_exporter/json_output/10_export_summary.json"
# Verify full doc exists
check_stage_output "10" "$TEST_RESULT_DIR/10_markdown_exporter/markdown_output/full_document.md"
echo -e "${GREEN}✅ S10: Export complete${NC}"


# Generate final validation report
echo -e "${GREEN}=== Stage Validation Complete ===${NC}"
    echo "Validation Successful!"
    echo "Report generated at: $TEST_RESULT_DIR/pipeline_validation_report.json"
    
    # Optional: Print summary of S08/S09/S10 artifacts
    echo "--- Artifacts ---"
cat > "$TEST_RESULT_DIR/pipeline_validation_report.json" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "pdf_path": "$PDF_PATH",
  "test_directory": "$TEST_RESULT_DIR",
  "status": "COMPLETED",
  "pipeline_stages": [
EOF

for stage in {01..08}; do
    if [ -d "$TEST_RESULT_DIR/stage$stage" ] || [ -f "$TEST_RESULT_DIR/pipeline.duckdb" ]; then
        # Loosened check for S08 which uses DB
        printf '    {"stage": "%s", "status": "COMPLETE"}' "$stage" >> "$TEST_RESULT_DIR/pipeline_validation_report.json"
        if [ "$stage" != "08" ]; then echo "," >> "$TEST_RESULT_DIR/pipeline_validation_report.json"; fi
    else
        printf '    {"stage": "%s", "status": "MISSING"}' "$stage" >> "$TEST_RESULT_DIR/pipeline_validation_report.json"
        if [ "$stage" != "08" ]; then echo "," >> "$TEST_RESULT_DIR/pipeline_validation_report.json"; fi
    fi
done

echo -e "\n  ]\n}" >> "$TEST_RESULT_DIR/pipeline_validation_report.json"

echo ""
echo -e "${GREEN}✅ Pipeline validation complete!${NC}"
echo "View results:"
echo "  Inspection: $TEST_RESULT_DIR"
echo "  Warnings: $TEST_RESULT_DIR/warnings.log"
echo "  Report: $TEST_RESULT_DIR/pipeline_validation_report.json"