# Comprehensive Review Request — Extractor (Pipeline + Core)

Fork: grahama1970/extractor
Branch: feat/section-heuristics-and-overlay
Path: git@github.com:grahama1970/extractor.git#feat/section-heuristics-and-overlay

Please run a full, production‑grade review of this repository with emphasis on the PDF pipeline (Stages 04–07) and supporting utils. Provide:
- Direct answers to the clarifying questions below.
- A prioritized issue list (blocker/major/minor) with concrete fixes.
- Unified diffs for proposed code changes (ready to apply).
- Any missing tests as code (drop‑in under `tests/`).
- Brief runbook notes for Stage 07 to ensure robust multimodal JSON output.

> Reviewer note: This request includes explicit failure context (what broke, how to reproduce, and what we’ve already tried). Please anchor your guidance and diffs to these repros.

## Context (Project Overview)
Extractor ingests PDFs and produces a structured “UnifiedDocument”. The current focus is pipeline robustness, determinism, and live VLM reflow:
- 04_section_builder: builds initial sections/blocks and section images.
- 05_table_extractor: Camelot + pandas metrics; deterministic ordering and `deterministic.json` added.
- 06_figure_extractor: extracts figure crops (+ optional VLM captions); reuses one open PDF; bounded concurrency; `deterministic.json` added.
- 07_reflow_section: large multimodal LLM/VLM reflow with strict JSON schema; pass‑through fallback exists; needs stronger schema‑safety.

LLM/VLM provider is Chutes (OpenAI‑compatible):
- Base URL: `CHUTES_API_BASE=https://llm.chutes.ai` (normalized to `/v1`).
- Model slots (env) currently set (examples):
  - `LITELLM_DEFAULT_MODEL="openai/zai-org/GLM-4.5-Air"`
  - `LITELLM_MED_VLM_MODEL="openai/chutesai/Mistral-Small-3.1-24B-Instruct-2503"`
  - `LITELLM_LARGE_VLLM_MODEL="openai/deepseek-ai/DeepSeek-V3.1-Terminus"`
  - `LITELLM_MED_TEXT_MODEL="openai/zai-org/GLM-4.6-turbo"`
  - Provider bridge: if `CHUTES_API_BASE` and `CHUTES_API_KEY` are set, `OPENAI_BASE_URL`/`OPENAI_API_KEY` are auto‑derived in our adapter.

## Failures Observed (with Repro Steps)

1) Stage 07 multimodal JSON contract breaks (blocker)
- Symptom: LLM returns content that does not include the expected top‑level key for strict schema (e.g., `reflowed_json`), causing a RuntimeError and task cancellations.
- Model/base at time of failure: `openai/deepseek-ai/DeepSeek-V3-0324-turbo` @ `https://llm.chutes.ai/v1`.
- Evidence (log tail):
  - `ValueError: Stage 07: Expected 'reflowed_json' in model output for schema mode but it was missing.`
  - Followed by: `RuntimeError: Stage 07 failed: LLM call did not return usable JSON.`
  - Repeated `LiteLLM: Cannot add callback - would exceed MAX_CALLBACKS limit of 30` warnings during run.
- Reproduce locally:
  ```bash
  source .venv/bin/activate && set -a && source .env && set +a
  export LITELLM_VLM_MODEL="openai/deepseek-ai/DeepSeek-V3-0324-turbo"
  export MAX_CONCURRENT_LLM_CALLS=1
  export STAGE07_MAX_TOKENS=512
  # Normalize OpenAI base from CHUTES (avoids double /v1)
  if [[ "${CHUTES_API_BASE:-}" == */v1 ]]; then export OPENAI_BASE_URL="$CHUTES_API_BASE"; else export OPENAI_BASE_URL="${CHUTES_API_BASE:-https://llm.chutes.ai}/v1"; fi
  PYTHONPATH=./src \
  python src/extractor/pipeline/steps/07_reflow_section.py run \
    --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
    --tables   data/results/pipeline/05_table_extractor/json_output/05_tables.json \
    --figures  data/results/pipeline/06_figure_extractor/json_output/06_figures.json \
    --timeout 45 --mode strict \
    2>&1 | tee scripts/artifacts/stage07_live_run.log
  ```
- Artifacts: `scripts/artifacts/stage07_live_run.log` (pushed), partial outputs under `data/results/pipeline/07_reflow_section/`.

2) Aggregator 404s / model resolution (fixed but needs review)
- Symptom: earlier calls returned 404 `No matching chute/cord found!` due to a double `/v1` and unverified model IDs.
- Fix applied: base URL normalization + model discovery/probe scripts.
- Verify:
  ```bash
  python debug/chutes_list_models.py --filter deepseek
  python debug/chutes_probe_models.py -m deepseek-ai/DeepSeek-V3-0324-turbo  # ok:true
  python debug/chutes_probe_models.py -m zai-org/GLM-4.5-Air                 # ok:true
  ```

3) Noisy pandas warnings (minor)
- `DataFrame.applymap` deprecated warnings in 07; not a blocker but clutters logs and may mask real issues.

## What We Already Tried
- Pre-warm models and verify availability via aggregator:
  - Added `debug/chutes_list_models.py` and `debug/chutes_probe_models.py` (base normalization, accepts openai/… or raw ids).
  - Confirmed DeepSeek and GLM variants are live (`ok:true`).
- Tightened Stage 07 runtime:
  - `MAX_CONCURRENT_LLM_CALLS=1`, `--timeout 45`, `STAGE07_MAX_TOKENS=512` to reduce first-token and schema drift.
- Determinism scaffolding (other stages):
  - 05/06: deterministic.json with rounded bbox + stable sorting; bounded concurrency in 06 with single open PDF reuse.
- Routing guardrails:
  - In `litellm_call.py`, automatic `CHUTES_* -> OPENAI_*` bridging and a single fallback retry on 401/403/404.

## Hypotheses / Suspected Root Causes
- Stage 07 prompt shaping for large multimodal messages isn’t strict enough for some models (even with `wrap_json` downstream). Not all models honor OpenAI’s `response_format` or function‑calling reliably.
- Our extraction relies on a single top-level key; partial/streamed or verbose responses break schema.
- LiteLLM callback warnings (MAX_CALLBACKS=30) suggest handler accumulation across many tasks; may degrade reliability.
- Timeout too low for first call on large context; or max_tokens too tight for strict JSON.

## What We Want From You (beyond general review)
- A resilient Stage 07 message/response strategy that works across OpenAI‑compatible providers (JSON‑first, tool/function calls when available, text‑to‑JSON fallback otherwise) with code.
- A hardened parser that tolerates verbosity/streaming and still extracts a minimal valid JSON object (top-level schema enforced) — include code.
- A Router simplification proposal: per‑request `api_base` / `api_key` vs model‑list entries; eliminate custom provider flags if unnecessary.
- A fix for LiteLLM MAX_CALLBACKS warnings (where/how to register/unregister callbacks) and any concurrency guards.
- Optional: replace pandas `applymap` paths with modern equivalents to quiet warnings.

## Live Scenarios (What must keep working)
- Deterministic artifacts for stages 05/06/07: stable sorting; rounded bbox; `json_output/deterministic.json`.
- Stage 07 “strict JSON” mode (multimodal, section image + low‑conf table image + text context) with 45–90s timeouts and concurrency 1–2.
- Gold standards: `data/gold_standards/pipeline` (BHT CV32A65X.pdf). New golds will be added for `with_requirements.pdf`.

## Clarifying Questions
1) Stage 07 schema guard: What exact message/response pattern and extraction logic do you recommend to guarantee a top‑level key (e.g., `reflowed_json`) even under long, streamed multimodal outputs? Please include code (messages + robust parser with partial/stream fallback).
2) Prompt shaping: Where should section image(s), low‑confidence table image(s), and figure captions appear (system vs user; order) to maximize schema fidelity? Include a short template.
3) Retry/fallback policy: Specify precise rules for timeouts, invalid JSON, provider 5xx, and partial outputs. When should we switch to text‑only or pass‑through, and how do we mark that in artifacts?
4) Routing: Validate `src/extractor/pipeline/utils/litellm_call.py` model mapping and `api_base` handling; simplify if possible. Should we pass per‑request `api_base/api_key` instead of Router entries for reliability?
5) Determinism: Confirm tie‑break sorting across 05/06; call out any remaining non‑deterministic paths.
6) Tests: List the highest‑leverage unit/e2e tests we’re missing for 05/06/07 and provide the exact test code.
7) Performance: Identify top hotspots in 06/07 and propose bounded‑concurrency/batching improvements (with code).

## Repro Commands (single place)
```bash
# Env bootstrap
source .venv/bin/activate && set -a && source .env && set +a

# Model discovery + probe (avoids 404s and double /v1)
python debug/chutes_list_models.py --filter deepseek
python debug/chutes_probe_models.py -m deepseek-ai/DeepSeek-V3-0324-turbo
python debug/chutes_probe_models.py -m zai-org/GLM-4.5-Air

# Stage 07 strict run (current failing repro)
export LITELLM_VLM_MODEL="openai/deepseek-ai/DeepSeek-V3-0324-turbo"
export MAX_CONCURRENT_LLM_CALLS=1
export STAGE07_MAX_TOKENS=512
if [[ "${CHUTES_API_BASE:-}" == */v1 ]]; then export OPENAI_BASE_URL="$CHUTES_API_BASE"; else export OPENAI_BASE_URL="${CHUTES_API_BASE:-https://llm.chutes.ai}/v1"; fi
PYTHONPATH=./src python src/extractor/pipeline/steps/07_reflow_section.py run \
  --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
  --tables   data/results/pipeline/05_table_extractor/json_output/05_tables.json \
  --figures  data/results/pipeline/06_figure_extractor/json_output/06_figures.json \
  --timeout 45 --mode strict \
  2>&1 | tee scripts/artifacts/stage07_live_run.log
```

## Key Files / Paths To Review
- Pipeline steps:
  - src/extractor/pipeline/steps/04_section_builder.py
  - src/extractor/pipeline/steps/05_table_extractor.py
  - src/extractor/pipeline/steps/06_figure_extractor.py
  - src/extractor/pipeline/steps/07_reflow_section.py
- Pipeline utils:
  - src/extractor/pipeline/utils/litellm_call.py
  - src/extractor/pipeline/utils/unified_conversion.py
  - src/extractor/pipeline/utils/mode.py
  - src/extractor/pipeline/utils/litellm_cache.py
- Scenarios / eval:
  - scenarios/pipeline/step05_eval_agent.py
  - scenarios/pipeline/step06_eval_agent.py
- Debug tools (model validation):
  - debug/chutes_list_models.py
  - debug/chutes_probe_models.py
  - debug/vlm_probe.py

## Acceptance (What to return)
- A concise issue list with severity and rationale.
- Unified diffs ready to apply for fixes and test additions.
- A Stage 07 mini‑runbook to minimize first‑token delays and schema breaks.

## Artifacts (for reference)
- scripts/artifacts/pipeline_steps_bundle.txt (source bundle)
- scripts/artifacts/stage07_live_run.log (latest run)
- data/results/pipeline/05_table_extractor/json_output/deterministic.json
- data/results/pipeline/06_figure_extractor/json_output/deterministic.json
- data/results/pipeline/07_reflow_section/json_output/07_reflowed.json (when present)

## Agent Failure Retrospective (Transparency)
- I initially appended `/v1` to a base that already contained `/v1`, causing 404s; fixed with normalization in the debug tools and env bridging.
- I tried a full Stage 07 run before validating model IDs; added list/probe scripts and confirmed working IDs.
- I used strict schema checks without a robust text‑to‑JSON fallback for verbose model outputs; request your diffs to harden this path.
- I observed LiteLLM callback accumulation warnings but did not yet instrument where callbacks are registered; request guidance.

Thanks — please provide answers + diffs. If tradeoffs are required, prefer minimal invasive changes first.
