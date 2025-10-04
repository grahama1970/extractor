# Comprehensive Review Request — Extractor Pipeline (Stages 04–07)

Fork: grahama1970/extractor
Branch: feat/section-heuristics-and-overlay
Path: git@github.com:grahama1970/extractor.git#feat/section-heuristics-and-overlay

Please perform a full, production-grade review of the pipeline steps under:
- src/extractor/pipeline/steps

Respond with:
- Direct answers to each question below
- Concrete recommendations, ordered by impact
- Unified diffs for proposed changes
- Any missing tests and the exact test code you recommend

## Context (High-Level)
Extractor assembles structured knowledge from PDFs. Relevant stages:
- 04_section_builder: baseline sections and text blocks
- 05_table_extractor: Camelot (lattice-first), pandas metrics; deterministic summary added
- 06_figure_extractor: figure crops + optional VLM descriptions; bounded concurrency; deterministic summary added
- 07_reflow_section: large multimodal reflow via LLM/VLM; JSON schema strict; pass-through fallback when requested

Live LLM/VLM provider: Chutes (OpenAI-compatible), base URL normalized to https://llm.chutes.ai/v1 via env.

Key env (.env) model slots currently used:
- LITELLM_DEFAULT_MODEL="openai/zai-org/GLM-4.5-Air"
- LITELLM_SMALL_VLM_MODEL="openai/chutesai/Mistral-Small-3.1-24B-Instruct-2503"
- LITELLM_MED_VLM_MODEL="openai/chutesai/Mistral-Small-3.1-24B-Instruct-2503"
- LITELLM_LARGE_VLLM_MODEL="openai/deepseek-ai/DeepSeek-V3.1-Terminus"
- LITELLM_SMALL_TEXT_MODEL="openai/zai-org/GLM-4.5-Air"
- LITELLM_MED_TEXT_MODEL="openai/zai-org/GLM-4.6-turbo"
- LITELLM_LARGE_TEXT_MODEL="openai/deepseek-ai/DeepSeek-R1"

Provider bridging: if CHUTES_API_BASE and CHUTES_API_KEY are set, OPENAI_BASE_URL and OPENAI_API_KEY are derived automatically in litellm_call.

## Current Pain Points
- Stage 07: intermittently returns non-schema JSON for large multimodal prompts (missing top-level key like reflowed_json). Needs stronger response-format control, streaming robustness, and fallbacks.
- Router config churn: historical double “/v1” base URL added to 404s; fixed, but request a sanity review of `litellm_call.py` routing and retries.
- Determinism: pass-through artifacts added, but confirm tie-break sorting across 05/06 before write.

## What To Review (Paths)
- src/extractor/pipeline/steps/05_table_extractor.py
- src/extractor/pipeline/steps/06_figure_extractor.py
- src/extractor/pipeline/steps/07_reflow_section.py
- src/extractor/pipeline/utils/litellm_call.py
- src/extractor/pipeline/utils/unified_conversion.py
- src/extractor/pipeline/utils/mode.py
- src/extractor/pipeline/utils/litellm_cache.py
- debug/chutes_list_models.py
- debug/chutes_probe_models.py

Bundle for quick context:
- scripts/artifacts/pipeline_steps_bundle.txt

## Scenarios / Live Features To Keep Working
- Deterministic runs: produce deterministic.json for 05/06/07 (stable ordering; rounded bbox coordinates)
- Live VLM runs (Stage 07):
  - Base URL: CHUTES_API_BASE (normalize to /v1)
  - Model IDs: prefer openai/<vendor>/<id> for Router; aggregator accepts raw <vendor>/<id>
  - Concurrency: MAX_CONCURRENT_LLM_CALLS=1–2
  - Timeout per section: 45–90s
- Gold standards:
  - data/gold_standards/pipeline for BHT CV32A65X.pdf
  - Will add with_requirements.pdf golds next; ensure schema stable

## Clarifying Questions (please answer explicitly)
1) Stage 07 JSON contract: propose a minimal-but-sufficient strict schema and a robust extraction strategy for partial/streamed responses. Include code.
2) Multimodal prompt shaping: exact message layout (system+user), and where to include table/figure snippets vs. images to maximize schema reliability.
3) Retry / fallback: exact policy for: invalid JSON, timeouts, provider 5xx, tool failures; when to switch to text-only or pass-through.
4) Router settings: confirm final OpenAI adapter parameters per model; suggest simplifying model mapping and per-call overrides.
5) Determinism: confirm table/figure sorting and tie-breaks; specify any edge cases left.
6) Tests: list unit/e2e tests we’re missing for 05/06/07, with suggested fixtures.
7) Performance: identify top hotspots in 06/07 and propose bounded-concurrency + batching shapes with code.

## Acceptance (What We Want Back)
- A concise issue list with severity (blocker/major/minor)
- Unified diffs we can apply directly (no large refactors unless essential)
- Tests as code snippets we can drop into tests/
- A short runbook for Stage 07 to minimize first-token delays and schema breaks

## Artifacts
- scripts/artifacts/pipeline_steps_bundle.txt
- scripts/artifacts/stage07_live_run.log (latest)
- data/results/pipeline/05_table_extractor/json_output/deterministic.json
- data/results/pipeline/06_figure_extractor/json_output/deterministic.json
- data/results/pipeline/07_reflow_section/json_output/07_reflowed.json (may be partial if failed)

Thanks — please return answers + diffs.
