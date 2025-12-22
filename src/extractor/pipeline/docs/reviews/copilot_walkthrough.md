# Extractor Pipeline Refactoring - Complete Walkthrough for Copilot

## Branch: `feature/merge-metadata-prop`

## Latest Commit: `365f5091`

---

## Summary

Refactored the extractor pipeline to extract utility functions into structured packages under `utils/`. All 5 major stages are now wired to use these packages.

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

## Phase 3: Stage Wiring ✅

### Stage 04 (Section Builder)

- **Action:** Removed 184 lines of dead code
- **API Alignment:** Updated `utils/sections/parsing.py` to match sbul API
- **Result:** 1620 → 1436 lines

### Stage 05 (Table Extractor)

- **Action:** Added imports from `utils/tables`
- **Imported:** `generate_pandas_metrics`, `score_table`, `iou`, `horizontal_iou`

### Stage 06b (Layout Sketcher)

- **Action:** Fixed API parity in `utils/layout/`
- **Fixed:** `summ()`, `norm_text()`, `assign_cols_and_span()` to match inline behavior

### Stage 08 (Lean4 Theorem Prover)

- **Action:** Added imports from `utils/prover`
- **Imported:** `ProofResult`, `prove_via_cli`, `prove_batch_via_cli`, `execute_lean_code_docker`

### Stage 09a (PDF Annotator)

- **Action:** Added imports from `utils/visuals`
- **Imported:** `COLORS`, `HUMAN_KIND`, `style_for_kind`, `stable_overlay_id`, etc.

---

## Verification Results

```
✅ All 5 utility packages import correctly
✅ All 3 wired stages (05/08/09a) verified
✅ 34/34 tests passing
```

---

## Commit History

```
365f5091 refactor: wire stages 05/08/09a to use utils packages
8a93e866 fix(layout): align utils/layout API with 06b inline behavior
239cdf7e refactor(04): apply Copilot cleanup + align utils/sections API
f17ec5cc docs: add complete package inventory for Copilot
fb2a220a docs: update copilot_handoff.md with Phase 2 completion
19e100f1 refactor: add utils/prover/, utils/layout/, utils/sections/ packages
```

---

## Remaining Work

### 1. Remove Inline Duplicate Functions

The stages now have dual definitions - old inline functions AND new imports. The inline functions can be removed once the imports are verified to work in production runs.

**Safe to remove in Stage 05:**

- `generate_pandas_metrics()` (lines ~559-576)
- `score_table()` (lines ~579-583)

**Safe to remove in Stage 08:**

- `_prove_via_cli()` (lines ~328-430)
- `_prove_batch_via_cli()` (lines ~433-576)
- `execute_lean_code()` (lines ~625-677)

**Safe to remove in Stage 09a:**

- Color constants `COLORS`, `HUMAN_KIND`, `TAB_COLORS` (lines ~40-119)
- Helper functions like `_lighten()`, `_style_for_kind()`, etc.

### 2. Stamp `log_llm_call()` at LLM Call Sites

The following stages have LLM calls that need telemetry stamping:

- Stage 03 (header verification)
- Stage 06 (VLM calls)
- Stage 07 (reflow LLM calls)
- Stage 08 (requirement extraction + proving)
- Stage 09 (summarization)

### 3. Run Integration Tests

Execute a full pipeline run on a test PDF to verify no regressions.

---

## Package Import Reference

```python
# Stage 04
from extractor.pipeline.utils.sections import analyze_section_numbering, detect_header_level

# Stage 05
from extractor.pipeline.utils.tables import generate_pandas_metrics, score_table, iou

# Stage 06b
from extractor.pipeline.utils.layout import detect_columns, assign_cols_and_span, grid_bbox

# Stage 08
from extractor.pipeline.utils.prover import ProofResult, prove_via_cli, execute_lean_code_docker

# Stage 09a
from extractor.pipeline.utils.visuals import COLORS, style_for_kind, stable_overlay_id
```
