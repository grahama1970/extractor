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

Thanks — please provide answers + diffs. If tradeoffs are required, prefer minimal invasive changes first.
