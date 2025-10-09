Fork: grahama1970/extractor
Branch: feat/step07-iteration3-diffs
Path: git@github.com:grahama1970/extractor.git#feat/step07-iteration3-diffs

Title: Comprehensive Review Request — src/extractor/pipeline/steps (LLM/VLM wiring, timeouts, determinism)

Context
- We hardened Stage‑07 and added Chutes warm‑start/debug scripts. We also reduced the default Router timeout in `litellm_call.py` to 45s to avoid perceived hangs.
- Models (.env) map to Chutes via OpenAI-compatible IDs for the Router path:
  - LITELLM_DEFAULT_MODEL="openai/zai-org/GLM-4.5-Air"
  - LITELLM_MED_TEXT_MODEL="openai/zai-org/GLM-4.6-turbo"
  - LITELLM_SMALL_VLM_MODEL="openai/chutesai/Mistral-Small-3.1-24B-Instruct-2503"
  - LITELLM_LARGE_VLLM_MODEL="openai/deepseek-ai/DeepSeek-V3.1-Terminus"

Live features & scenarios to keep in mind
- Stage 05/06 deterministic artifacts (deterministic.json), fixed sort order; Stage 06 bounded concurrency.
- Stage 07 validators (07b/07c/07d) simplified and env-tunable; 07f STRICT_KEY_NAMESPACE guard; timeouts/retries clarified.
- Debug harness under `debug/chutes/` to verify provider warm start and Router health.

Please review (files under src/extractor/pipeline/steps):
- 05_table_extractor.py — deterministic summary writing, ordering, error handling.
- 06_figure_extractor.py — single PDF open, semaphore concurrency, deterministic summary.
- 07b_paragraph_polish.py — validator, env overrides, prompt plumbing.
- 07c_table_title_infer.py — title validator and model selection.
- 07d_figure_caption_refine.py — caption validator and model selection.
- 07f_arango_export.py — STRICT_KEY_NAMESPACE checks.
- utils: `utils/litellm_call.py` timeout defaults and retry logic; budget/metrics if present.

Questions to answer
1) Are Router/request timeouts applied correctly to streaming and non-streaming paths? Any missing backoff/retry-after handling?
2) Do 07b/07c/07d validators correctly prevent placeholder/low‑signal outputs without over‑rejecting?
3) Is the deterministic mode story consistent across 05/06/07 output artifacts?
4) Are there code paths where exceptions could bypass final sorting or artifact writes?
5) Any opportunities to factor common timeout/retry/env parsing across steps?

Requested output
- A brief analysis per file (bulleted).
- Unified diffs for proposed changes (minimally invasive), especially:
  - Timeout/backoff parity in streaming branch of `litellm_call.py`.
  - Any cleanup in 05/06 deterministic writing and error paths.
  - Validator tweaks with rationale.
  - STRICT_KEY_NAMESPACE additional assertions if needed.

Relevant paths
- src/extractor/pipeline/steps/05_table_extractor.py
- src/extractor/pipeline/steps/06_figure_extractor.py
- src/extractor/pipeline/steps/07b_paragraph_polish.py
- src/extractor/pipeline/steps/07c_table_title_infer.py
- src/extractor/pipeline/steps/07d_figure_caption_refine.py
- src/extractor/pipeline/steps/07f_arango_export.py
- src/extractor/pipeline/utils/litellm_call.py
- debug/chutes/* (diagnostics only)

Artifacts for reference
- debug/artifacts/curl_models.json
- debug/artifacts/curl_ping_text_provider2.json
- debug/artifacts/warm_probe_text.log
- debug/artifacts/warm_probe_text.json

Thanks! Please include reasoning for each proposed change and provide unified diffs we can apply.

