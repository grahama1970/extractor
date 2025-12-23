# Copilot Handoff: LLM Telemetry + Pipeline Refactoring

**Branch:** `feature/merge-metadata-prop`  
**Latest Commit:** `19e100f1`  
**Updated:** 2025-12-22

---

## ✅ Phase 1: Schema & Helper (Complete)

### `schemas/llm_call.py` — LLMCallRecord Schema

```python
class LLMCallRecord(BaseModel):
    ts: str                                    # ISO timestamp
    stage: str                                 # "07_reflow_section"
    task_kind: str                             # "reflow", "summarize", etc.
    route: Literal["chutes/text", "chutes/vlm"]
    model: str
    section_id: str | None = None
    success: bool
    error_class: str | None = None             # "timeout", "parse_fail", etc.
    latency_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    attempt_count: int | None = None
    raw_preview: str | None = None
```

### `debug_utils.log_llm_call()` — Helper

```python
from extractor.pipeline.utils.debug_utils import log_llm_call

log_llm_call(
    stage_key="07_reflow_section",
    task_kind="reflow",
    route="chutes/text",
    model=get_text_model(),
    success=True,
    section_id="sec_001",
    latency_ms=1500,
    tokens_in=100,
    tokens_out=200,
)
```

---

## ✅ Phase 2: Utility Packages (Complete)

**7 packages created, 3,528 lines extracted:**

| Package           | Stage | Lines | Key Functions                        |
| ----------------- | ----- | ----- | ------------------------------------ |
| `utils/reflow/`   | 07    | 1,217 | prompts, tables, layout, llm_helpers |
| `utils/headers/`  | 03    | 380   | heuristics, llm, priors              |
| `utils/tables/`   | 05    | 618   | extraction, metrics, heuristics      |
| `utils/visuals/`  | 09a   | 559   | colors, geometry, formatting         |
| `utils/prover/`   | 08    | 259   | execution (CLI/Docker)               |
| `utils/layout/`   | 06b   | 289   | geometry, columns                    |
| `utils/sections/` | 04    | 206   | parsing (numbering, titles)          |

**Commits:**

- `c36c1c9a` — utils/headers/
- `14e1d40b` — utils/tables/, utils/visuals/, step_refactors docs
- `19e100f1` — utils/prover/, utils/layout/, utils/sections/

---

## ❌ Phase 3: Remaining Work for Copilot

### Task A: Wire Imports + Delete Duplicates

For each stage, `07_reflow_section.py` etc:

1. Add imports from the new `utils/` package
2. Delete the inline duplicate function definitions
3. Expected reduction: ~16,000 → ~2,600 lines

### Task B: Stamp LLM Call Sites

| Stage | task_kind           | Call Sites                                           |
| ----- | ------------------- | ---------------------------------------------------- |
| 03    | `"verify_header"`   | `verify_header_with_llm()`                           |
| 06    | `"figure_describe"` | VLM calls                                            |
| 07    | `"reflow"`          | `_direct_scillm_json()`, `reflow_section_with_llm()` |
| 08    | `"lean4_formalize"` | `identify_requirements_in_section()`                 |
| 09    | `"summarize"`       | `_direct_scillm_summary_call()`                      |

### Task C: Tests

- Run `pytest tests/pipeline/schemas/` — currently 34/34 passing
- Run smoke test after wiring imports

---

## Step Refactor Documentation

Detailed plans for each stage are in:

```
src/extractor/pipeline/docs/step_refactors/
├── README.md          # Overview
├── stage05.md         # Table Extractor
├── stage06_sketcher.md
├── stage08_lean4.md
├── stage09_refactor.md
└── stage09a_annotator.md
```

---

## Recommended Order

1. **Wire imports** for one stage (e.g., 07)
2. **Delete duplicates** from that stage
3. **Add `log_llm_call()` stamps** to that stage
4. **Test** → repeat for other stages

## 🛑 Phase 4: Emergency Repairs & Assessment (Dec 2025)

**Status**: The pipeline compilation and wiring has been repaired. The "refactoring" in Phase 2 left many runner files in a broken state (missing imports, undefined variables, missing helper functions). These have been mechanically fixed to pass `offline-smoke` tests.

### "Brutal" Assessment

**Is it AI Slop?**

- **Borderline.** The Phase 2 refactor exhibited "hallucination-like" traits: creating runner files that _looked_ correct structurally but failed to import critical dependencies or define local helpers.
- **Example**: `utils/layout/sketcher.py` was missing ~15 internal helper functions (`_norm`, `_grid_bbox`) that were left behind in the original step file.
- **Example**: `utils/report_runner.py` crashed on `list` vs `int` comparison for `section_depth`, indicating a lack of type discipline/validation across stages.

**Can it be saved?**

- **YES.** The underlying architecture (Sequential Steps → Runners → Shared Utils) is sound and much better than the original monolith.
- **It works now.** The pipeline passed a full end-to-end `offline-smoke` test on Dec 23, 2025.
- **Do NOT rewrite from scratch.** Use the current working state as a baseline and harden it.

### Revised Request for Next Agent

**Goal**: Transform the "working but fragile" pipeline into a robust, type-safe system.

1.  **Strict Data Contracts**:

    - Implement Pydantic models for _all_ inter-stage JSON artifacts (`04_sections.json`, `07_reflowed.json`, etc.).
    - Eliminate "mixed types" (e.g. ensure `section_depth` is always `int` or `List[int]`, not both).
    - Validate inputs at the start of every `runner.run()` function.

2.  **Logic Hardening (Cleanup)**:

    - The "Injection" logic in `utils/layout/sketcher.py` (helpers copied from step) is technical debt. Move these to a proper utility module (e.g. `extractor.pipeline.utils.geometry`).
    - Audit all `utils/*.py` files for "aspirational" code (unused imports, stubs).

3.  **Online Verification**:

    - `offline-smoke` passes, but Stages 08 (Prover) and 09 (Summarizer) were skipped.
    - **CRITICAL**: Run a _live_ test (or high-fidelity mock) to verify that `log_llm_call` and the LLM logic in `utils/reflow/section_reflow.py` actually work.

4.  **Logging**:
    - Complete "Task B" (Stamp LLM Call Sites) if it hasn't been done. Ensure telemetry is capturing costs/latency.

**Conclusion**: The patient is stable but needs intensive care (types, tests) before discharge.
