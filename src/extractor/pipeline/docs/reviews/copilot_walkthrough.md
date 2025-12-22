# Extractor Pipeline Refactoring - Complete Walkthrough for Copilot

## Branch: `feature/merge-metadata-prop`

## Latest Commit: `ab0d938a`

---

## Summary

Refactored the extractor pipeline to extract utility functions into structured packages under `utils/`. Stages 03, 04, 05, 08, and 09a are now properly wired. Telemetry integration has started with Stage 03.

---

## Phase 1: Schema + Telemetry ✅

| Component         | Location               | Description                            |
| ----------------- | ---------------------- | -------------------------------------- |
| `LLMCallRecord`   | `schemas/llm_call.py`  | Pydantic schema for LLM call telemetry |
| `log_llm_call()`  | `utils/debug_utils.py` | Helper for logging LLM calls           |
| `log_and_raise()` | `utils/reliability.py` | Consistent error handling pattern      |

---

## Phase 2: Utility Packages Created ✅

| Package           | Lines | Target Stage | Key Exports                                                    |
| ----------------- | ----- | ------------ | -------------------------------------------------------------- |
| `utils/reflow/`   | 1,217 | Stage 07     | `consolidate_data()`, prompt builders, table merging           |
| `utils/headers/`  | 380   | Stage 03     | `verify_header_with_llm()`, heuristics                         |
| `utils/tables/`   | 618   | Stage 05     | `generate_pandas_metrics()`, `score_table()`, `iou()`          |
| `utils/visuals/`  | 559   | Stage 09a    | `COLORS`, `style_for_kind()`, `stable_overlay_id()`            |
| `utils/prover/`   | 259   | Stage 08     | `ProofResult`, `prove_via_cli()`, `execute_lean_code_docker()` |
| `utils/layout/`   | 289   | Stage 06b    | `detect_columns()`, `assign_cols_and_span()`, `grid_bbox()`    |
| `utils/sections/` | 270   | Stage 04     | `analyze_section_numbering()`, `detect_header_level()`         |

**Total extracted:** 3,592 lines

---

## Phase 3: Stage Wiring & Cleanup ✅

### Stage 03 (Suspicious Headers) - FULLY WIRED + TELEMETRY

- **Status**: Wired to `utils/headers/llm`. Inline logic removed.
- **Telemetry**: Uses `log_llm_call` in utility.
- **Reduction**: 1732 → ~1574 lines (~158 lines removed).
- **Fix**: Fixed potential bug in batch result normalization by using utility's standard return format.

### Stage 04 (Section Builder) - FULLY WIRED

- **Status**: Wired to `utils/sections`. Dead code removed.
- **Reduction**: 1620 → 1436 lines (-184 lines).
- **Verified**: Commit `9422459b` confirms correct wiring.

### Stage 05 (Table Extractor) - FULLY WIRED

- **Status**: Wired to `utils/tables`. Inline duplicates removed.
- **Reduction**: 2456 → 2431 lines (-25 lines).
- **Verified**: Call sites use `_generate_pandas_metrics`, `_score_table`.

### Stage 08 (Lean4 Theorem Prover) - FULLY WIRED

- **Status**: Wired to `utils/prover`. Inline duplicates removed (execution logic).
- **Reduction**: 1634 → 1331 lines (-303 lines).
- **Telemetry**: LLM generation part still needs telemetry stamping.

### Stage 09a (PDF Annotator) - FULLY DE-DUPLICATED

- **Status**: Wired to `utils/visuals`. All inline components removed.
- **Reduction**: 2305 → 1985 lines (-320 lines total).
- **Verified**: Fully clean. Evidence in `src/extractor/pipeline/docs/reviews/copilot_verification_evidence.md` (if needed).

---

## Verification Results

```
✅ Stage 03: verify_header_with_llm using utils.headers.llm
✅ Stage 04: analyze_section_numbering using utils.sections
✅ Stage 05: _generate_pandas_metrics using utils.tables
✅ Stage 08: _execute_lean_code_docker using utils.prover
✅ Stage 09a: All helpers using utils.visuals (full deduplication)
✅ 34/34 tests passing
✅ Total cleanup: ~990 lines removed
```

---

## Commit History

```
ab0d938a refactor(03): wire to utils/headers/llm and add telemetry
cdb0539a docs: update Copilot walkthrough
cab5825b refactor(09a): full deduplication of visual helpers
02f48c21 docs: update Copilot walkthrough
85e79cdf refactor(09a): remove inline color/style duplicates
4712a438 refactor(08): remove inline CLI/docker functions
b7ad2c3c refactor(05): remove inline generate_pandas_metrics/score_table
9422459b refactor(04): wire Stage 04 to utils/sections
```

---

## Remaining Work

### 1. Stamp `log_llm_call()` at Remaining LLM Call Sites

- Stage 06 (VLM calls)
- Stage 07 (reflow LLM calls)
- Stage 08 (generation - currently inline)
- Stage 09 (summarization)

### 2. Wire Stage 06, 07

- **Stage 06**: Add VLM telemetry
- **Stage 07**: Wire to `utils/reflow/`
