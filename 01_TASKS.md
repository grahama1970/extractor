# Pipeline Steps Fix Tasks

> Generated: 2026-01-16
> Quality Gate: Enabled (runs on task completion via ~/.claude/hooks)

## Overview

Assessment found **4 blocking issues** and **8 high-priority issues** across 19 pipeline steps.

---

## BLOCKING ISSUES (Must Fix First)

### TASK-001: Fix s05b_table_describer typo (Line 210)
- **File:** `src/extractor/pipeline/steps/s05b_table_describer.py`
- **Line:** 210
- **Issue:** `getattr(time, "time")()` should be `time.time()`
- **Impact:** Runtime error on every execution
- **Fix:** Replace `getattr(time, "time")()` with `time.time()`

### TASK-002: Fix s02_marker_extractor duplicate returns (Lines 407, 410)
- **File:** `src/extractor/pipeline/steps/s02_marker_extractor.py`
- **Line:** 407, 410
- **Issue:** Duplicate `return out_path` statements
- **Impact:** Dead code, potential logic error
- **Fix:** Remove duplicate return statement

### TASK-003: Fix s01_annotation_processor missing import (Line 466)
- **File:** `src/extractor/pipeline/steps/s01_annotation_processor.py`
- **Line:** 466
- **Issue:** `require_scillm_preflight()` called but not imported
- **Impact:** NameError on execution
- **Fix:** Add import or remove call if not needed

### TASK-004: Fix s07_duckdb_ingest function call (Line 543)
- **File:** `src/extractor/pipeline/steps/s07_duckdb_ingest.py`
- **Line:** 543
- **Issue:** `suppress_overlapping_blocks(con, tables_json)` called with wrong parameters
- **Impact:** Potential runtime error or incorrect behavior
- **Fix:** Verify function signature and correct call

---

## HIGH PRIORITY (Missing sanity() Functions)

### TASK-005: Add sanity() to s00_profile_detector
- **File:** `src/extractor/pipeline/steps/s00_profile_detector.py`
- **Issue:** Missing `sanity()` function required by framework
- **Fix:** Add `def sanity() -> int: return run_step_sanity(STEP_NAME)`

### TASK-006: Add sanity() to s04_section_builder
- **File:** `src/extractor/pipeline/steps/s04_section_builder.py`
- **Issue:** Missing `sanity()` function
- **Fix:** Add sanity function with basic validation

### TASK-007: Add sanity() to s08_extract_requirements
- **File:** `src/extractor/pipeline/steps/s08_extract_requirements.py`
- **Issue:** Missing standalone `sanity()` function
- **Fix:** Add sanity function

### TASK-008: Add sanity() to s09_section_summarizer
- **File:** `src/extractor/pipeline/steps/s09_section_summarizer.py`
- **Issue:** Missing `sanity()` function
- **Fix:** Add sanity function

---

## MEDIUM PRIORITY (Code Quality)

### TASK-009: Fix s04a_layout_audit unreachable code (Line 48-49)
- **File:** `src/extractor/pipeline/steps/s04a_layout_audit.py`
- **Line:** 48-49
- **Issue:** Code after `raise` in `_read_json()` is unreachable
- **Fix:** Remove unreachable code or restructure logic

### TASK-010: Fix s14_report_generator duplicate function
- **File:** `src/extractor/pipeline/steps/s14_report_generator.py`
- **Lines:** 273-338 and 455-523
- **Issue:** Duplicate `generate_comprehensive_report()` definition
- **Fix:** Remove duplicate, keep the correct implementation

### TASK-011: Fix s05_table_extractor duplicate import (Line 83)
- **File:** `src/extractor/pipeline/steps/s05_table_extractor.py`
- **Line:** 83
- **Issue:** Duplicate `stitch_headers` import
- **Fix:** Remove duplicate import

### TASK-012: Remove s07_duckdb_ingest deprecated code
- **File:** `src/extractor/pipeline/steps/s07_duckdb_ingest.py`
- **Issue:** `merge_page_break_tables()` marked DEPRECATED but still present
- **Fix:** Remove deprecated function if unused

---

## LOW PRIORITY (Cleanup)

### TASK-013: Fix s06_figure_extractor no-op parameter
- **File:** `src/extractor/pipeline/steps/s06_figure_extractor.py`
- **Line:** 156
- **Issue:** `skip_descriptions` parameter is ignored (no-op)
- **Fix:** Either implement or remove parameter

### TASK-014: Clean up s06b_figure_describer commented code
- **File:** `src/extractor/pipeline/steps/s06b_figure_describer.py`
- **Lines:** 181-183
- **Issue:** Commented-out cleanup code
- **Fix:** Remove or uncomment based on intent

### TASK-015: Fix s08_lean4_theorem_prover stub (Line 103)
- **File:** `src/extractor/pipeline/steps/s08_lean4_theorem_prover.py`
- **Line:** 103
- **Issue:** `pass` stub - incomplete implementation
- **Fix:** Implement or document as intentional placeholder

---

## PRESET CONTEXT PROPAGATION (Include in Sprint)

### TASK-016: Add preset_config to s04a_layout_audit
- **File:** `src/extractor/pipeline/steps/s04a_layout_audit.py`
- **Fix:** Accept and propagate preset_config parameter

### TASK-017: Add preset_config to s05b_table_describer
- **File:** `src/extractor/pipeline/steps/s05b_table_describer.py`
- **Fix:** Accept preset_config, use for VLM prompts if applicable

### TASK-018: Add preset_config to s05c_table_merger
- **File:** `src/extractor/pipeline/steps/s05c_table_merger.py`
- **Fix:** Accept and propagate preset_config parameter

### TASK-019: Add preset_config to s06_figure_extractor
- **File:** `src/extractor/pipeline/steps/s06_figure_extractor.py`
- **Fix:** Accept and propagate preset_config parameter

### TASK-020: Add preset_config to s06b_figure_describer
- **File:** `src/extractor/pipeline/steps/s06b_figure_describer.py`
- **Fix:** Accept preset_config, use for VLM prompts if applicable

### TASK-021: Add preset_config to s07_duckdb_ingest
- **File:** `src/extractor/pipeline/steps/s07_duckdb_ingest.py`
- **Fix:** Accept and store preset_config in pipeline context

### TASK-022: Add preset_config to s07b_text_cleaner
- **File:** `src/extractor/pipeline/steps/s07b_text_cleaner.py`
- **Fix:** Accept and propagate preset_config parameter

### TASK-023: Add preset_config to s08_lean4_theorem_prover
- **File:** `src/extractor/pipeline/steps/s08_lean4_theorem_prover.py`
- **Fix:** Use preset_config.features.enable_proving to control execution

### TASK-024: Add preset_config to s10_markdown_exporter
- **File:** `src/extractor/pipeline/steps/s10_markdown_exporter.py`
- **Fix:** Accept preset_config for format-specific options

### TASK-025: Add preset_config to s10_arangodb_exporter
- **File:** `src/extractor/pipeline/steps/s10_arangodb_exporter.py`
- **Fix:** Accept preset_config for graph schema options

### TASK-026: Add preset_config to s14_report_generator
- **File:** `src/extractor/pipeline/steps/s14_report_generator.py`
- **Fix:** Include preset info in generated reports

---

## Execution Order

1. TASK-001 through TASK-004 (Blocking - fix first)
2. TASK-005 through TASK-008 (High Priority - sanity functions)
3. TASK-009 through TASK-012 (Medium - code quality)
4. TASK-013 through TASK-015 (Low - cleanup)
5. TASK-016 through TASK-026 (Preset propagation)

## Quality Gate

Each task completion triggers:
```
~/.claude/hooks/task-complete-gate.sh → quality-gate.sh → pytest/make test
```

Tests must pass before marking task complete.
