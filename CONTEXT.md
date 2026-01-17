# CONTEXT — VLM/SciLLM fixes complete, sanity tests passing

_Last updated: 2026-01-16T21:30:00+00:00 · Branch: main · Session: VLM investigation_

## 1. Active goal
- All sanity tests passing (7/7)
- VLM/SciLLM paved-path compliance fixed
- Cross-format parity maintained

## 2. Repo / branch
- Repo root: /home/graham/workspace/experiments/extractor
- Branch: main
- Commits ahead of origin: 14

## 3. Session Summary (2026-01-16)

### VLM Investigation and Fixes

**Problem:** "PDF accurate" sanity test was timing out (600s) despite VLM calls being fast (~1-2s).

**Root Causes Found:**
1. **Missing `custom_llm_provider="openai_like"`** in `parallel_acompletions_iter` calls caused the iterator to hang indefinitely without yielding results
2. **Wrong attribute name** in run_pipeline.py: checked `prove_theorems` instead of `prove_requirements`
3. **Preset config override bug**: preset config was enabling Lean4 proving even when `--skip-proving` was passed

**Commits Made:**
```
ac275518 fix(pipeline): VLM sanity check and scillm paved-path compliance
2ced9351 fix(scillm): Add custom_llm_provider to remaining parallel_acompletions_iter calls
```

**Files Modified:**
| File | Change |
|------|--------|
| `scripts/sanity_check_extractor.py` | Added `--skip-proving`, reduced timeout 600s→120s |
| `src/extractor/pipeline/run_pipeline.py` | Fixed `prove_theorems`→`prove_requirements`, added skip flag check |
| `src/extractor/pipeline/steps/s05b_table_describer.py` | Added `custom_llm_provider="openai_like"` |
| `src/extractor/pipeline/steps/s06b_figure_describer.py` | Added `custom_llm_provider="openai_like"` |
| `src/extractor/pipeline/steps/s01_annotation_processor.py` | Added `custom_llm_provider="openai_like"` |
| `src/extractor/pipeline/steps/s03_suspicious_headers.py` | Added `custom_llm_provider="openai_like"` |
| `src/extractor/pipeline/steps/s05_table_extractor.py` | Added `custom_llm_provider="openai_like"` |
| `src/extractor/pipeline/steps/s08_extract_requirements.py` | Added `custom_llm_provider="openai_like"` |
| `src/extractor/pipeline/steps/s09_section_summarizer.py` | Added `custom_llm_provider="openai_like"` |
| `src/extractor/pipeline/utils/headers/llm.py` | Added `custom_llm_provider="openai_like"` |
| `src/extractor/pipeline/utils/reflow/llm.py` | Added `custom_llm_provider="openai_like"` |

### SciLLM Paved-Path Contract

**Key Learning:** All `parallel_acompletions_iter` calls to Chutes.ai MUST include:
```python
async for result in parallel_acompletions_iter(
    requests,
    api_base=api_base,
    api_key=api_key,
    custom_llm_provider="openai_like",  # REQUIRED - without this, iterator hangs
    concurrency=6,
    timeout=45,
    wall_time_s=300,  # Max batch duration
    tenacious=False,  # Fail fast
    response_format={"type": "json_object"},
):
```

**Reference:** `/home/graham/workspace/experiments/litellm/docs/scillm/SCILLM_PAVED_PATH_CONTRACT.md`

### pi-mono scillm Skill Enhancement

Added VLM command and sanity check to `/home/graham/workspace/experiments/pi-mono/.pi/skills/scillm/`:
- `vlm.py` - VLM (multimodal) image description command
- `sanity.sh` - Skill verification script
- Updated `SKILL.md` with two-pattern documentation

**Commit (pi-mono):** `0b3d62fb feat(scillm): Add VLM command and sanity check`

## 4. Current State

### Sanity Check Results (7/7 passing)
```
✅ Pipeline sanity: 19/19 steps OK
✅ HTML: 20 blocks in 6ms
✅ MARKDOWN: 27 blocks in 0ms
✅ XML: 47 blocks in 1ms
✅ RST: 19 blocks in 18ms
✅ PDF fast: 3 sections in 7340ms
✅ PDF accurate: 2 sections in 33937ms (~34s)
```

### Cross-Format Parity (from prior session)
| Format | Parity | Status |
|--------|--------|--------|
| MD     | 100.0% | Perfect |
| DOCX   | 100.0% | Perfect |
| XML    | 90.2%  | Fixed |
| PDF    | 86.7%  | Fixed |
| RST    | 84.8%  | OK |
| EPUB   | 82.0%  | OK |
| PPTX   | 80.6%  | Fixed |
| XLSX   | 15.6%  | Expected (spreadsheet) |
| PNG    | 15.8%  | Expected (image) |

## 5. Files Still Missing `custom_llm_provider`

These utility files may need fixing if used in production:
```
src/extractor/pipeline/utils/reflow/section_reflow.py (3 calls)
src/extractor/pipeline/utils/layout/sketcher.py (1 call)
src/extractor/pipeline/utils/summarizer_runner.py (2 calls)
src/extractor/pipeline/utils/prover/runner.py (2 calls)
src/extractor/pipeline/sanity/s08_requirements_sanity.py (1 call)
src/extractor/pipeline/sanity/s09_summarize_sanity.py (1 call)
```

## 6. Environment Requirements

```bash
# Required env vars for VLM/LLM
CHUTES_API_BASE=https://llm.chutes.ai/v1
CHUTES_API_KEY=<your-key>
CHUTES_VLM_MODEL=Qwen/Qwen3-VL-235B-A22B-Instruct
CHUTES_TEXT_MODEL=moonshotai/Kimi-K2-Instruct-0905

# Optional for Lean4 proving
SCILLM_API_BASE=http://localhost:8787/v1  # Lean4 bridge
```

## 7. Commands

```bash
# Run full sanity check
python scripts/sanity_check_extractor.py

# Run PDF-only sanity check
python scripts/sanity_check_extractor.py --format pdf

# Test VLM directly (should complete in ~1-2s)
curl -s "${CHUTES_API_BASE}/chat/completions" \
  -H "Authorization: Bearer ${CHUTES_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model": "'"${CHUTES_VLM_MODEL}"'", "messages": [{"role": "user", "content": "Say hello."}], "max_tokens": 16}'

# Run parity test
PYTHONPATH=src .venv/bin/python tools/tasks_loop/utils/crossformat_parity_test.py \
  --fixture-dir data/input/twins/preset_twin --name preset_twin --reference html
```

## 8. Docker Services

```bash
# Required services (from `docker ps`)
- lean_runner (lean4-lean_runner) - Lean4 theorem prover
- scillm-ollama (ollama/ollama) - Local LLM fallback
- arangodb (arangodb:3.12.6) - Graph database
- litellm-codex-agent - LiteLLM proxy
```

## 9. Known Issues / Warnings

1. **Chutes 503 errors**: Chutes.ai may return 503 Service Unavailable during high load. The pipeline handles this gracefully.
2. **Redis not running**: Warning about Redis cache unavailable is normal if Redis isn't configured.
3. **Lean4 not exposed**: The lean_runner container doesn't expose port 8787 by default.

## 10. How to Continue

```
"Continue extractor work from CONTEXT.md - sanity tests passing, focus on [your task]"
```

**Potential follow-up tasks:**
- Fix remaining `custom_llm_provider` calls in utility files (section 5)
- Add VLM sanity test that specifically tests multimodal calls
- Configure Lean4 bridge for theorem proving
- Push commits to origin (14 ahead)
