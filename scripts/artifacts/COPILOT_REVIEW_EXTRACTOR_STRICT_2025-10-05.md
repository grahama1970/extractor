Fork: grahama1970/extractor
Branch: feat/strict-stage07-tenacity
Path: git@github.com:grahama1970/extractor.git#feat/strict-stage07-tenacity

Request: Comprehensive code review of the entire extractor pipeline (PDF/HTML/Markdown), with emphasis on:
- Stage 06/07 reliability under provider rate limiting
- Determinism and schema consistency across stages
- Logging, backoff/retry policy, and failure transparency
- Performance of figure extraction/rasterization and reflow prompts

Context:
- Environment: Python 3.11, venv, .env with CHUTES_API_BASE=/v1 and CHUTES_API_KEY
- VLM Models: SMALL=Mistral-Small-3.1-24B, MED=Qwen2.5-VL-72B, LARGE=Qwen3-VL-235B
- Changes just made (this branch):
  - litellm_call: tenacity-backed retries (429/5xx/timeouts), Router num_retries=0, Retry-After floor logging, file sink at data/results/pipeline/logs/litellm_call.log
    - src/extractor/pipeline/utils/litellm_call.py
  - Stage 07: strict JSON parsing improvements; auto-wrap when model returns {blocks: [...]} or list-of-blocks; early-safe helpers; env snapshot logging
    - src/extractor/pipeline/steps/07_reflow_section.py
  - Stage 06: env snapshot logging; figure description path uses tiered models
    - src/extractor/pipeline/steps/06_figure_extractor.py
  - Stage 03: clean PDF selection prefers s02 basename to avoid wrong document
    - src/extractor/pipeline/steps/03_suspicious_headers.py
  - New utility: env_debug.log_env_snapshot
    - src/extractor/pipeline/utils/env_debug.py

Scenarios to consider:
- with_requirements.pdf: run 02→07 strict; confirm Stage 06 captions present; Stage 07 produces reflowed JSON; no hidden fallbacks
- High-latency/429 cases: ensure Retry-After honored; logs include attempt/backoff; no concurrency spikes
- HTML/Markdown inputs: verify synthetic pages/bboxes; ensure Stage 07 schema parity

Clarifying questions for the reviewer:
1) Is the tenacity policy correctly scoped (no double retries) and logging sufficient to diagnose burst 429s?
2) Should Stage 07 use a stricter response_format (json object) per provider, or keep relaxed + hardened parsing?
3) Is the auto-wrap behavior for {blocks: [...]}/list-of-blocks acceptable, or should we require explicit reflowed_json?
4) Any race conditions in PDF open/reuse or figure concurrency that we missed? Suggestions for caps per-doc?
5) Determinism: Recommend any hashes/ordering we should add to Stage 07 outputs similar to 05/06?

Relevant paths:
- Pipeline runner: src/extractor/pipeline/run_all.py
- Steps: src/extractor/pipeline/steps/0*/**.py (especially 03, 05, 06, 07)
- Utils: src/extractor/pipeline/utils/*.py (litellm_call, response_utils, env_debug)

Please respond with:
- Findings grouped by Reliability, Correctness, Performance, Maintainability, Security
- File/line references (relative paths) and suggested unified diffs for fixes
- Any recommended acceptance tests and smoke scripts (commands ok)
