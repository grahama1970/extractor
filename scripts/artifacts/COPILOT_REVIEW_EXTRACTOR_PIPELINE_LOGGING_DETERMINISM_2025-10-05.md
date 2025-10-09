Fork: grahama1970/extractor
Branch: feat/step07-iteration3-diffs
Path: git@github.com:grahama1970/extractor.git#feat/step07-iteration3-diffs

Title: Review Request — Pipeline Logging, Determinism, and Router Hardening

Context
- We added stage start/end JSONL event logging, deterministic sorting + content hashes, centralized validation metadata, and a Retry‑After floor for the litellm Router path.
- Goal: ensure logs are sufficient for triage, outputs are stable across runs, and Router paths avoid “silent hang” or retry loops.

Changes in this PR (high‑level)
- New utility: src/extractor/pipeline/utils/pipeline_event_logger.py
  - Emits JSONL events to data/results/pipeline/pipeline_events.log.
- Stage 02/03/05/06: deterministic output ordering and structural content hashes.
- Stage 07b/07c/07d: centralized validation_meta while preserving existing __meta keys (back‑compat).
- Stage 07f: extended strict edge allow‑list.
- litellm_call: Retry‑After coercion (env floor), all‑failed batch warning; stream/non‑stream wait_for already present.

Artifacts for this run
- warm probe/logs in debug/artifacts (from earlier step):
  - warm_probe_text.json, warm_probe_text.log, list_models_head.txt
- pipeline events file will accumulate during stage runs:
  - data/results/pipeline/pipeline_events.log

Questions
1) Logging coverage: Any crucial locations still missing (e.g., 07a/07e/07h/07m internal entry/exit)? Recommend additions.
2) Determinism: Any other ordering we should lock (e.g., 03 page merging edge cases, 07 block merges) before write?
3) Validation metadata: Is the centralized validation_meta map acceptable as a long‑term contract? If not, propose an alternative and provide a minimal diff.
4) litellm_call: Should we also log a concise per‑batch summary (success/failed counts by model) and where? Please supply a small diff.
5) Arango allow‑list: Are the new collections sufficient, or do you foresee additional ones we should include now?

Files for Review
- src/extractor/pipeline/utils/pipeline_event_logger.py
- src/extractor/pipeline/steps/02_marker_extractor.py
- src/extractor/pipeline/steps/03_suspicious_headers.py
- src/extractor/pipeline/steps/05_table_extractor.py
- src/extractor/pipeline/steps/06_figure_extractor.py
- src/extractor/pipeline/steps/07b_paragraph_polish.py
- src/extractor/pipeline/steps/07c_table_title_infer.py
- src/extractor/pipeline/steps/07d_figure_caption_refine.py
- src/extractor/pipeline/steps/07f_arango_export.py
- src/extractor/pipeline/utils/litellm_call.py

Request
- Please provide answers and unified diffs for suggested improvements.

