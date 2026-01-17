# CONTEXT — Assessment Complete, SciLLM Paved-Path Compliance Fixed

_Last updated: 2026-01-17T08:30:00+00:00 · Branch: main · Session: Assessment & Fixes_

## 1. Active Goal
- All sanity tests passing (7/7)
- All `custom_llm_provider` calls fixed (10 files)
- `--preset` flag implemented for skip-detection mode
- pi-mono extractor skill enhanced with sanity.sh

## 2. Repo / branch
- Repo root: /home/graham/workspace/experiments/extractor
- Branch: main
- Commits ahead of origin: 14+ (uncommitted changes)

## 3. Session Summary (2026-01-17)

### Assessment Results

**Cross-Format Parity (measured 2026-01-17):**
| Format | Parity | Status |
|--------|--------|--------|
| MD | 100.0% | Perfect |
| DOCX | 100.0% | Perfect |
| HTML | Reference | Baseline |
| XML | 90.2% | Good |
| PDF | 86.7% | Good |
| RST | 84.8% | Good |
| EPUB | 82.0% | Good |
| PPTX | 80.6% | Acceptable |
| XLSX | 15.6% | Expected (spreadsheet) |
| PNG | 15.8% | Expected (image/VLM) |

### Fixes Applied

**1. All `custom_llm_provider="openai_like"` calls fixed:**
| File | Calls Fixed |
|------|-------------|
| `utils/summarizer_runner.py` | 2 |
| `utils/reflow/section_reflow.py` | 3 |
| `utils/layout/sketcher.py` | 1 |
| `utils/prover/runner.py` | 2 |
| `sanity/s08_requirements_sanity.py` | 1 |
| `sanity/s09_summarize_sanity.py` | 1 |

**2. `--preset` flag implemented:**
```bash
# Skip s00 auto-detection, force preset directly
python -m extractor.pipeline paper.pdf --preset arxiv
python -m extractor.pipeline spec.pdf --preset requirements_spec
```

**3. pi-mono extractor skill enhanced:**
- Created `sanity.sh` - tests all 10 formats
- Updated `SKILL.md` - accurate parity percentages
- Added LLM requirements documentation

### SciLLM Paved-Path Contract

**Required pattern for all Chutes.ai calls:**
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

## 4. Current State

### Sanity Check Results (7/7 passing)
```
✅ Pipeline sanity: 19/19 steps OK
✅ HTML: 20 blocks in 6ms
✅ MARKDOWN: 27 blocks in 0ms
✅ XML: 47 blocks in 1ms
✅ RST: 19 blocks in 18ms
✅ PDF fast: 3 sections in 7354ms
✅ PDF accurate: 2 sections in 35011ms
```

### Supported Formats (10 total)
- **High parity (85%+):** MD, DOCX, HTML, XML, PDF, RST
- **Good parity (80%+):** EPUB, PPTX
- **Expected low (16%):** XLSX, PNG (structural differences)

## 5. Files Modified This Session

**Extractor project:**
- `src/extractor/pipeline/run_pipeline.py` - Added `--preset` flag
- `src/extractor/pipeline/utils/summarizer_runner.py` - Added custom_llm_provider
- `src/extractor/pipeline/utils/reflow/section_reflow.py` - Added custom_llm_provider (3 calls)
- `src/extractor/pipeline/utils/layout/sketcher.py` - Added custom_llm_provider
- `src/extractor/pipeline/utils/prover/runner.py` - Added custom_llm_provider (2 calls)
- `src/extractor/pipeline/sanity/s08_requirements_sanity.py` - Added custom_llm_provider
- `src/extractor/pipeline/sanity/s09_summarize_sanity.py` - Added custom_llm_provider

**pi-mono skill:**
- `.pi/skills/extractor/sanity.sh` - Created sanity test script
- `.pi/skills/extractor/SKILL.md` - Updated parity claims
- `.pi/skills/extractor/extract.py` - Enabled --preset flag passthrough

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

# Run PDF with forced preset (skip auto-detection)
python -m extractor.pipeline paper.pdf --preset arxiv --use-llm

# Run parity test
PYTHONPATH=src .venv/bin/python tools/tasks_loop/utils/crossformat_parity_test.py \
  --fixture-dir data/input/twins/preset_twin --name preset_twin --reference html

# Test pi-mono skill
/home/graham/workspace/experiments/pi-mono/.pi/skills/extractor/sanity.sh
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
- Push commits to origin (14+ ahead)
- Add VLM sanity test that specifically tests multimodal calls
- Configure Lean4 bridge for theorem proving
- Create README.md for pi-mono extractor skill
