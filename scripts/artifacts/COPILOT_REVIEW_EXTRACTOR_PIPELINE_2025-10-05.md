Fork: grahama1970/extractor
Branch: feat/step07-iteration3-diffs
Path: git@github.com:grahama1970/extractor.git#feat/step07-iteration3-diffs

Title: Comprehensive Review — Extractor Pipeline (Steps 02–07 + LLM Router)

Scope
- Steps: 02, 03, 05, 06, 07 (07a–07m inside 07_reflow_section where applicable)
- Utils: litellm_call (Router wrapper), supporting cache/log/image utils

Live Context & Scenarios
- Target PDFs: pipeline fixture(s) under data/pdfs/ (gold standards exist for BHT CV32A65X.pdf).
- Stage requirements (LLM/VLM): 03 header verification, 06 figure description (VLM optional), 07 reflow/normalization (LLM/VLM), 09 summaries (out of current scope).
- Live model routing: Chutes via OpenAI-compatible path (OPENAI_BASE_URL=…/v1). Default text model: openai/zai-org/GLM-4.5-Air. Vision as needed via env.

Recent Changes to Review (highlights)
- Determinism & summaries: 05/06 sorted outputs; 05 failed-artifact on PDF open error.
- Validation metadata: 07b/07c/07d now attach validation_reason for rejected candidates.
- Arango strictness: 07f enforces allowed edge collections and _from/_to collection prefixes under STRICT_KEY_NAMESPACE.
- Watchdogs: litellm_call wraps Router calls in asyncio.wait_for for streaming and non-streaming.
- Logging pass:
  - 05/06/07b/07c/07d/07f: start + LLM-fire + summary logs (items, conc, timeouts, model, counts).
  - 07_reflow_section: start log, no-sections warning, per-subset summary (paragraphs/tables/figures), reflow_mode.
  - 03: proper log on empty task path; 02: start log, safer excepts, ruff-safe tweaks where brittle.

Artifacts
- Warm path checks (executed today):
  - debug/artifacts/warm_probe_text.json
  - debug/artifacts/warm_probe_text.log
  - debug/artifacts/list_models_head.txt
- Provider curl sanity: debug/chutes/curl_chat_ping.sh output (stdout logged during run)

Questions (please answer with rationale and unified diffs where appropriate)
1) Logging coverage
   - Are there critical locations we missed (e.g., per-sub-stage 07a/07e/07h/07m entry/exit where failures cluster)?
   - Should any logs be downgraded (info→debug) or upgraded (warning→error) to align with runbook triage?
2) Determinism
   - Any remaining non-deterministic ordering or tie-break paths in 05/06/07 that still need sorting before write?
3) litellm_call
   - Is the wait_for placement correct for both streaming and non-streaming? Any missing branch (images-only, export=results)?
   - We observed a litellm Retry-After TypeError (min_timeout None). Would you recommend setting LITELLM_RETRY_AFTER≥0.5, or patching Router kwargs to ensure min timeouts are numeric? Please include a minimal diff suggestion.
4) Validation metadata
   - Is the pid__meta/tid__meta/fid__meta pattern acceptable, or do you prefer a separate metadata map to avoid key-space clutter?
5) Arango strictness
   - Are our allowed edge collections complete for this phase? Suggest an allow-list update or guard.
6) Failure modes
   - Suggest small guardrails for early returns that currently skip writing a structured failure artifact (beyond 05 open error).

Files to Review (relative paths)
- src/extractor/pipeline/steps/02_marker_extractor.py
- src/extractor/pipeline/steps/03_suspicious_headers.py
- src/extractor/pipeline/steps/05_table_extractor.py
- src/extractor/pipeline/steps/06_figure_extractor.py
- src/extractor/pipeline/steps/07_reflow_section.py
- src/extractor/pipeline/steps/07b_paragraph_polish.py
- src/extractor/pipeline/steps/07c_table_title_infer.py
- src/extractor/pipeline/steps/07d_figure_caption_refine.py
- src/extractor/pipeline/steps/07f_arango_export.py
- src/extractor/pipeline/utils/litellm_call.py

Acceptance: Please provide numbered answers and unified diffs for proposed changes. If suggesting structural shifts, keep them minimal and scoped with a short rationale.

