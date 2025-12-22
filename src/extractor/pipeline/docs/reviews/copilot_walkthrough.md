# Extractor Pipeline Refactoring - Complete Walkthrough for Copilot

## Branch: `feature/merge-metadata-prop`

## Latest Commit: `9422459b`

---

## Summary

Refactored the extractor pipeline to extract utility functions into structured packages under `utils/`. All major stages are now properly wired to use these packages.

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

### Stage 04 (Section Builder) - FULLY WIRED

```python
from extractor.pipeline.utils.sections import (
    SECTION_NUMBER_PATTERNS,
    analyze_section_numbering,
    detect_header_level,
    extract_section_title,
    ...
)
```

- **Verified:** `analyze_section_numbering.__module__` = `utils.sections.parsing`
- sbul retained only for: `normalize_breadcrumbs`, `breadcrumb_label`, `enrich_header_colors`, `prepare_section_hierarchy`

### Stage 05 (Table Extractor) - Imports Added

```python
from extractor.pipeline.utils.tables import (
    generate_pandas_metrics as _generate_pandas_metrics,
    score_table as _score_table,
    iou as _table_iou,
)
```

### Stage 06b (Layout Sketcher) - API Aligned

- `utils/layout/`: `summ()`, `norm_text()`, `assign_cols_and_span()` match inline behavior

### Stage 08 (Lean4 Theorem Prover) - Imports Added

```python
from extractor.pipeline.utils.prover import (
    ProofResult, prove_via_cli, execute_lean_code_docker,
)
```

### Stage 09a (PDF Annotator) - Imports Added

```python
from extractor.pipeline.utils.visuals import (
    COLORS, style_for_kind, stable_overlay_id, ...
)
```

---

## Verification Results

```
✅ Stage 04: analyze_section_numbering from utils.sections.parsing
✅ Stage 05: _generate_pandas_metrics from utils.tables.metrics
✅ Stage 08: _ProofResult from utils.prover.execution
✅ Stage 09a: imports verified
✅ 34/34 tests passing
```

---

## Commit History

```
9422459b refactor(04): wire Stage 04 to utils/sections per Copilot analysis
3a0468d9 docs: add comprehensive Copilot walkthrough for refactoring
365f5091 refactor: wire stages 05/08/09a to use utils packages
8a93e866 fix(layout): align utils/layout API with 06b inline behavior
239cdf7e refactor(04): apply Copilot cleanup + align utils/sections API
```

---

## Remaining Work

### 1. Remove Inline Duplicate Functions in 05/08/09a

Stages now have dual definitions. Safe to remove:

- **Stage 05:** `generate_pandas_metrics()`, `score_table()`
- **Stage 08:** `_prove_via_cli()`, `execute_lean_code()`
- **Stage 09a:** Color/formatting functions

### 2. Stamp `log_llm_call()` at LLM Call Sites

Stages with LLM calls needing telemetry: 03, 06, 07, 08, 09

### 3. Wire Stage 03, 06, 07

Stage 03: `utils/headers/`
Stage 06: Add VLM telemetry
Stage 07: `utils/reflow/`
