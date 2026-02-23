# Pipeline Steps Fix Tasks

> Generated: 2026-01-16
> Quality Gate: Enabled (runs on task completion via ~/.claude/hooks)
> **Last Verified: 2026-02-04** - All blocking and high-priority tasks COMPLETE

## Overview

~~Assessment found **4 blocking issues** and **8 high-priority issues** across 19 pipeline steps.~~

**STATUS UPDATE (2026-02-04):** All blocking issues and sanity() functions have been implemented.
- 516 tests collected
- 21 pipeline steps have sanity() functions
- All imports verified working

---

## BLOCKING ISSUES (Must Fix First) - ✅ ALL COMPLETE

### TASK-001: Fix s05b_table_describer typo (Line 210) ✅ COMPLETE
- **File:** `src/extractor/pipeline/steps/s05b_table_describer.py`
- **Line:** 210
- **Issue:** `getattr(time, "time")()` should be `time.time()`
- **Impact:** Runtime error on every execution
- **Fix:** Replace `getattr(time, "time")()` with `time.time()`
- **Status:** FIXED - code now uses `time.time()` correctly at line 219

### TASK-002: Fix s02_marker_extractor duplicate returns (Lines 407, 410) ✅ COMPLETE
- **File:** `src/extractor/pipeline/steps/s02_marker_extractor.py`
- **Line:** 407, 410
- **Issue:** Duplicate `return out_path` statements
- **Impact:** Dead code, potential logic error
- **Fix:** Remove duplicate return statement
- **Status:** FIXED - no duplicate returns present

### TASK-003: Fix s01_annotation_processor missing import (Line 466) ✅ COMPLETE
- **File:** `src/extractor/pipeline/steps/s01_annotation_processor.py`
- **Line:** 466
- **Issue:** `require_scillm_preflight()` called but not imported
- **Impact:** NameError on execution
- **Fix:** Add import or remove call if not needed
- **Status:** FIXED - call removed, clean return statement

### TASK-004: Fix s07_duckdb_ingest function call (Line 543) ✅ COMPLETE
- **File:** `src/extractor/pipeline/steps/s07_duckdb_ingest.py`
- **Line:** 543
- **Issue:** `suppress_overlapping_blocks(con, tables_json)` called with wrong parameters
- **Impact:** Potential runtime error or incorrect behavior
- **Fix:** Verify function signature and correct call
- **Status:** FIXED - line 543 is now a logger.info statement

---

## HIGH PRIORITY (Missing sanity() Functions) - ✅ ALL COMPLETE

### TASK-005: Add sanity() to s00_profile_detector ✅ COMPLETE
- **File:** `src/extractor/pipeline/steps/s00_profile_detector.py`
- **Issue:** Missing `sanity()` function required by framework
- **Fix:** Add `def sanity() -> int: return run_step_sanity(STEP_NAME)`
- **Status:** IMPLEMENTED at line 562

### TASK-006: Add sanity() to s04_section_builder ✅ COMPLETE
- **File:** `src/extractor/pipeline/steps/s04_section_builder.py`
- **Issue:** Missing `sanity()` function
- **Fix:** Add sanity function with basic validation
- **Status:** IMPLEMENTED at line 1427

### TASK-007: Add sanity() to s08_extract_requirements ✅ COMPLETE
- **File:** `src/extractor/pipeline/steps/s08_extract_requirements.py`
- **Issue:** Missing standalone `sanity()` function
- **Fix:** Add sanity function
- **Status:** IMPLEMENTED at line 1127

### TASK-008: Add sanity() to s09_section_summarizer ✅ COMPLETE
- **File:** `src/extractor/pipeline/steps/s09_section_summarizer.py`
- **Issue:** Missing `sanity()` function
- **Fix:** Add sanity function
- **Status:** IMPLEMENTED at line 559

---

## MEDIUM PRIORITY (Code Quality) - ✅ ALL VERIFIED (2026-02-04)

### TASK-009: Fix s04a_layout_audit unreachable code (Line 48-49) ✅ FALSE POSITIVE
- **File:** `src/extractor/pipeline/steps/s04a_layout_audit.py`
- **Line:** 48-49
- **Issue:** Code after `raise` in `_read_json()` is unreachable
- **Fix:** Remove unreachable code or restructure logic
- **Status:** FALSE POSITIVE - `return {}` at line 49 IS reachable when `path.exists()` is False

### TASK-010: Fix s14_report_generator duplicate function ✅ ALREADY FIXED
- **File:** `src/extractor/pipeline/steps/s14_report_generator.py`
- **Lines:** 273-338 and 455-523
- **Issue:** Duplicate `generate_comprehensive_report()` definition
- **Fix:** Remove duplicate, keep the correct implementation
- **Status:** FIXED - Only ONE function at line 711, duplicates removed

### TASK-011: Fix s05_table_extractor duplicate import (Line 83) ✅ ALREADY FIXED
- **File:** `src/extractor/pipeline/steps/s05_table_extractor.py`
- **Line:** 83
- **Issue:** Duplicate `stitch_headers` import
- **Fix:** Remove duplicate import
- **Status:** FIXED - No duplicate import at line 83

### TASK-012: Remove s07_duckdb_ingest deprecated code ✅ ALREADY FIXED
- **File:** `src/extractor/pipeline/steps/s07_duckdb_ingest.py`
- **Issue:** `merge_page_break_tables()` marked DEPRECATED but still present
- **Fix:** Remove deprecated function if unused
- **Status:** FIXED - No DEPRECATED marker or function found

---

## LOW PRIORITY (Cleanup) - ✅ ALL VERIFIED (2026-02-04)

### TASK-013: Fix s06_figure_extractor no-op parameter ✅ ALREADY FIXED
- **File:** `src/extractor/pipeline/steps/s06_figure_extractor.py`
- **Line:** 156
- **Issue:** `skip_descriptions` parameter is ignored (no-op)
- **Fix:** Either implement or remove parameter
- **Status:** FIXED - Parameter removed entirely

### TASK-014: Clean up s06b_figure_describer commented code ✅ ALREADY FIXED
- **File:** `src/extractor/pipeline/steps/s06b_figure_describer.py`
- **Lines:** 181-183
- **Issue:** Commented-out cleanup code
- **Fix:** Remove or uncomment based on intent
- **Status:** FIXED - Lines 181-183 now contain active error handling code

### TASK-015: Fix s08_lean4_theorem_prover stub (Line 103) ✅ ACCEPTABLE
- **File:** `src/extractor/pipeline/steps/s08_lean4_theorem_prover.py`
- **Line:** 103
- **Issue:** `pass` stub - incomplete implementation
- **Fix:** Implement or document as intentional placeholder
- **Status:** ACCEPTABLE - `pass` is inside diagnostic logging exception handler, intentional to prevent crashes from non-critical logging failures

---

## PRESET CONTEXT PROPAGATION (Include in Sprint) - ✅ ALL COMPLETE (2026-02-04)

**Verification:** `grep -l "preset_config" src/extractor/pipeline/steps/*.py | wc -l` = **14 files**

### TASK-016: Add preset_config to s04a_layout_audit ✅ COMPLETE
### TASK-017: Add preset_config to s05b_table_describer ✅ COMPLETE
### TASK-018: Add preset_config to s05c_table_merger ✅ COMPLETE
### TASK-019: Add preset_config to s06_figure_extractor ✅ COMPLETE
### TASK-020: Add preset_config to s06b_figure_describer ✅ COMPLETE
### TASK-021: Add preset_config to s07_duckdb_ingest ✅ COMPLETE
### TASK-022: Add preset_config to s07b_text_cleaner ✅ COMPLETE
### TASK-023: Add preset_config to s08_lean4_theorem_prover ✅ COMPLETE
### TASK-024: Add preset_config to s10_markdown_exporter ✅ COMPLETE
### TASK-025: Add preset_config to s10_arangodb_exporter ✅ COMPLETE
### TASK-026: Add preset_config to s14_report_generator ✅ COMPLETE

All 14 pipeline step files now have `preset_config` support:
- s04_section_builder.py, s04a_layout_audit.py
- s05_table_extractor.py, s05b_table_describer.py, s05c_table_merger.py
- s06_figure_extractor.py, s06b_figure_describer.py
- s07_duckdb_ingest.py, s07b_text_cleaner.py
- s08_lean4_theorem_prover.py, s09_section_summarizer.py
- s10_markdown_exporter.py, s10_arangodb_exporter.py, s14_report_generator.py

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

---

## Definition of Done (Per Task)

### TASK-001 through TASK-004 (Blocking Issues)
- **Test**: `pytest tests/pipeline/steps/test_cli_factories_all_steps.py -v`
- **Assertion**: All steps import without errors, no runtime exceptions

### TASK-005 through TASK-008 (Sanity Functions)
- **Test**: `python -c "from extractor.pipeline.steps import <step>; print(<step>.sanity())"`
- **Assertion**: Each sanity() function returns 0 (pass)

### TASK-009 through TASK-015 (Code Quality)
- **Test**: `make smokes-cli` (runs full test suite)
- **Assertion**: 0 test failures, no import/runtime errors

### TASK-016 through TASK-026 (Preset Propagation)
- **Test**: `pytest tests/pipeline/ -v -k preset`
- **Assertion**: Preset config propagates through all steps without errors
- **Note**: Full verification requires end-to-end pipeline run with preset

### All Tasks
- **Common Gate**: `pytest tests/ --collect-only` collects 180+ tests with 0 errors
- **Common Gate**: `make smokes-cli` exits with code 0
