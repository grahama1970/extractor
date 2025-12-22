# Copilot Handoff: LLM Telemetry Implementation

## ✅ Already Implemented (by Antigravity)

### 1) `schemas/llm_call.py` — LLMCallRecord Schema

```python
class LLMCallRecord(BaseModel):
    ts: str                                    # ISO timestamp (auto-added)
    stage: str                                 # "07_reflow_section"
    task_kind: str                             # "reflow", "summarize", etc.
    route: Literal["chutes/text", "chutes/vlm"]
    model: str                                 # from get_text_model() / get_vlm_model()
    section_id: str | None = None
    success: bool
    error_class: str | None = None             # "timeout", "parse_fail", "validation_fail"
    latency_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    attempt_count: int | None = None           # null = unknown (as you suggested)
    raw_preview: str | None = None             # only on error, max 400 chars

    model_config = {"extra": "forbid"}
```

### 2) `debug_utils.log_llm_call()` — Helper Function

```python
from extractor.pipeline.utils.debug_utils import log_llm_call

log_llm_call(
    stage_key="07_reflow_section",
    task_kind="reflow",
    route="chutes/text",
    model=get_text_model(),  # from model_select.py
    success=True,
    section_id="sec_001",
    latency_ms=1500,
    tokens_in=100,
    tokens_out=200,
    # error_class, raw_preview only on failure
)
```

Writes to `{stage}/logs/timings.jsonl` via existing `log_timing()`.

### 3) Tests

- 34 schema tests passing
- Committed: `cf054175` on `feature/merge-metadata-prop`

---

## ❌ Still Needed: Stage Call Site Stamping

### Task Kind Vocabulary (confirmed)

| Stage         | task_kind                |
| ------------- | ------------------------ |
| 03 VLM        | `"verify_header"`        |
| 06 VLM        | `"figure_describe"`      |
| 07 text       | `"reflow"`               |
| 07r reqs      | `"extract_requirements"` |
| 08 Lean4      | `"lean4_formalize"`      |
| 09 summary    | `"summarize"`            |
| 09 checkpoint | `"checkpoint_summary"`   |

---

## Key Call Sites to Stamp

### Stage 03: `03_suspicious_headers.py`

```python
# Line ~890: VLM call in verify_header_with_llm()
router = get_vlm_router()
resp = await router.acompletion(messages=msgs, ...)
# ADD after call:
log_llm_call("03_suspicious_headers", "verify_header", "chutes/vlm", get_vlm_model(), ...)
```

### Stage 07: `07_reflow_section.py`

```python
# Line ~371-409: _direct_scillm_json()
router = get_text_router()
resp = await router.acompletion(...)
# ADD after call

# Line ~1318-3827: reflow_section_with_llm() - multiple router calls
# Each router.acompletion() needs stamping
```

### Stage 09: `09_section_summarizer.py`

```python
# Line ~200-270: _direct_scillm_summary_call()
router = get_text_router()
resp = await router.acompletion(...)
# Already has timing logic - extend with log_llm_call()
```

---

## Answers to Copilot's Questions

1. **attempt_count**: Use `None` (null) to make "unknown" explicit ✅
2. **model source**: Use `get_text_model()` / `get_vlm_model()` as canonical ✅
   - If `resp.model` available, could optionally add `served_model` field later
3. **PR approach**: Schema + helper already done; just need call site stamping

---

## File Size Blocker

~~The large stage files (07=5385 lines, 09=890 lines) still need Phase 2 extraction before Copilot can read them fully.~~

**UPDATE**: Phase 2 started. New `utils/reflow/` package created:

```
src/extractor/pipeline/utils/reflow/
├── __init__.py
├── tables.py   # 280 lines - merge logic, cell sanitization, confidence
├── layout.py   # 130 lines - IoU, figure blocks, layout ordering
├── prompts.py  # TODO - prompt formatting
├── llm_helpers.py  # TODO - router wrappers
└── data_loader.py  # TODO - consolidate_data
```

Copilot can proceed with:

1. Creating remaining modules (prompts.py, llm_helpers.py, data_loader.py)
2. Updating `07_reflow_section.py` imports to use new package
3. Removing extracted functions from `07_reflow_section.py`
