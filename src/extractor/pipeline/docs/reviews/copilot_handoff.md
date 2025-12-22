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
