# Extractor Pipeline Refactoring - Complete Walkthrough for Copilot

## Branch: `feature/merge-metadata-prop`

## Latest Commit: `85e79cdf`

---

## Summary

Refactored the extractor pipeline to extract utility functions into structured packages under `utils/`. Stages 04, 05, 08, and 09a are now properly wired to use these packages, with significant dead code removal.

---

## Phase 1: Schema + Telemetry ✅

| Component         | Location               | Description                            |
| ----------------- | ---------------------- | -------------------------------------- |
| `LLMCallRecord`   | `schemas/llm_call.py`  | Pydantic schema for LLM call telemetry |
| `log_llm_call()`  | `utils/debug_utils.py` | Helper function for logging LLM calls  |
| `log_and_raise()` | `utils/reliability.py` | Consistent error handling pattern      |

---

## Phase 2: Utility Packages Created ✅

| Package           | Lines | Target Stage | Key Exports                                                    |
| ----------------- | ----- | ------------ | -------------------------------------------------------------- |
| `utils/reflow/`   | 1,217 | Stage 07     | `consolidate_data()`, prompt builders, table merging           |
| `utils/headers/`  | 380   | Stage 03     | Header heuristics, LLM verification                            |
| `utils/tables/`   | 618   | Stage 05     | `generate_pandas_metrics()`, `score_table()`, `iou()`          |
| `utils/visuals/`  | 559   | Stage 09a    | `COLORS`, `style_for_kind()`, `stable_overlay_id()`            |
| `utils/prover/`   | 259   | Stage 08     | `ProofResult`, `prove_via_cli()`, `execute_lean_code_docker()` |
| `utils/layout/`   | 289   | Stage 06b    | `detect_columns()`, `assign_cols_and_span()`, `grid_bbox()`    |
| `utils/sections/` | 270   | Stage 04     | `analyze_section_numbering()`, `detect_header_level()`         |

**Total extracted:** 3,592 lines

---

## Phase 3: Stage Wiring & Cleanup ✅

### Stage 04 (Section Builder) - FULLY WIRED

- **Status**: Wired to `utils/sections`. Dead code removed.
- **Reduction**: 1620 → 1436 lines (-184 lines).
- **Imports**: `analyze_section_numbering`, `detect_header_level`.

### Stage 05 (Table Extractor) - FULLY WIRED

- **Status**: Wired to `utils/tables`. Inline duplicates removed.
- **Reduction**: 2456 → 2431 lines (-25 lines).
- **Removed**: Inline `generate_pandas_metrics`, `score_table`.
- **Imports**: `_generate_pandas_metrics`, `_score_table`.

### Stage 06b (Layout Sketcher) - API Aligned

- **Status**: Utility API aligned with stage behavior.
- **Imports**: `utils/layout` aligned, ready for wiring.

### Stage 08 (Lean4 Theorem Prover) - FULLY WIRED

- **Status**: Wired to `utils/prover`. Inline duplicates removed.
- **Reduction**: 1634 → 1331 lines (-303 lines).
- **Removed**: Inline `_prove_via_cli`, `_prove_batch_via_cli`, `execute_lean_code`.
- **Imports**: `_prove_via_cli`, `_execute_lean_code_docker`.

### Stage 09a (PDF Annotator) - FULLY WIRED

- **Status**: Wired to `utils/visuals`. Inline duplicates removed.
- **Reduction**: 2305 → 2252 lines (-53 lines).
- **Removed**: Inline `COLORS`, `HUMAN_KIND`, `_lighten`, `_style_for_kind`.
- **Imports**: `COLORS`, `HUMAN_KIND`, `style_for_kind` (aliased).

---

## Verification Results

```
✅ Stage 04: analyze_section_numbering using utils.sections
✅ Stage 05: _generate_pandas_metrics using utils.tables
✅ Stage 08: _execute_lean_code_docker using utils.prover
✅ Stage 09a: COLORS using utils.visuals
✅ 34/34 tests passing
✅ Total cleanup: ~565 lines removed
```

---

## Commit History

```
85e79cdf refactor(09a): remove inline color/style duplicates
4712a438 refactor(08): remove inline CLI/docker functions (-303 lines)
b7ad2c3c refactor(05): remove inline generate_pandas_metrics/score_table
d969610b docs: update walkthrough - Stage 04 now fully wired
9422459b refactor(04): wire Stage 04 to utils/sections
3a0468d9 docs: add comprehensive Copilot walkthrough for refactoring
```

---

## Remaining Work

### 1. Stamp `log_llm_call()` at LLM Call Sites

Stages with LLM calls needing telemetry:

- Stage 03 (header verification)
- Stage 06 (VLM calls)
- Stage 07 (reflow LLM calls)
- Stage 08 (requirement extraction)
- Stage 09 (summarization)

### 2. Wire Stage 03, 06, 07

- **Stage 03**: Wire to `utils/headers/`
- **Stage 06**: Add VLM telemetry
- **Stage 07**: Wire to `utils/reflow/`
