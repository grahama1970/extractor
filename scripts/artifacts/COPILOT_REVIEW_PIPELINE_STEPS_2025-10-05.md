Fork: grahama1970/extractor
Branch: feat/step07-iteration3-diffs
Path: git@github.com:grahama1970/extractor.git#feat/step07-iteration3-diffs

Title: Comprehensive Review Request — Pipeline Steps (05/06/07x) and LLM Call Watchdogs

Scope
- Full review of: src/extractor/pipeline/steps
- Plus supporting util: src/extractor/pipeline/utils/litellm_call.py

Context
- This pipeline extracts tables (05), figures (06), and performs reflow/LLM-driven refinements (07b/07c/07d) with an optional Arango export (07f).
- We hardened determinism, added minimal audit metadata, and introduced outer watchdogs to prevent perceived hangs in the LiteLLM Router path.

Live Verification Artifacts
- Raw curl sanity (provider path): see debug/chutes/curl_* (script prints JSON; verified success).
- Warm-start probe (Router/OpenAI path):
  - debug/artifacts/warm_probe_text.json
  - debug/artifacts/warm_probe_text.log
- Models listing (head):
  - debug/artifacts/list_models_head.txt

What changed (high level)
- 05_table_extractor.py
  - Deterministic ordering of output tables before write.
  - Failed-artifact emission when PDF open fails (05_tables_failed.json).
- 06_figure_extractor.py
  - Deduped initialization and deterministic ordering of extracted figures.
- 07b_paragraph_polish.py
  - Attach {pid__meta: {validation_reason}} when LLM candidate rejected.
- 07c_table_title_infer.py
  - Attach {tid__meta: {validation_reason}} when title invalid/generic.
- 07d_figure_caption_refine.py
  - Attach {fid__meta: {validation_reason}} when fallback to original caption occurs.
- 07f_arango_export.py
  - STRICT_KEY_NAMESPACE: allow-list for edge collections + _from/_to collection prefix checks.
- utils/litellm_call.py
  - Add asyncio.wait_for watchdog in streaming and non-streaming paths using timeout=(request_timeout or 45)+10s.

Acceptance Goals for Review
- Identify any correctness, determinism, or failure-path issues introduced by the above.
- Verify output schema stability: additions are strictly additive (do not break existing consumers).
- Confirm we are not leaking secrets in logs or artifacts.

Questions
1) 05/06 ordering: Any remaining spots where output order can vary when exceptions occur mid-run? Recommend minimal guards if found.
2) 07b/07c/07d validation_reason: Prefer alternative location for metadata (e.g., separate map) to avoid PID/ID key-space clutter?
3) litellm_call watchdog: Is the wait_for wrapped at the best level for both streaming and non-streaming? Any missed branch (e.g., images-only or results export)?
4) Retry-After handling: We saw a litellm TypeError in a rare branch (min_timeout None). Propose defaulting LITELLM_RETRY_AFTER to 0.5 or patching kwargs to ensure min timeout is numeric. Suggestions?
5) 07f strictness: Are the allowed edge collections and endpoint collection prefixes sufficient to catch schema drift without blocking valid edges we might add soon?

Please provide
- Point-by-point answers (numbered).
- Unified diffs for any proposed fixes or improvements.
- If suggesting structural changes, include minimal scoped diffs and a short rationale.

Files to Review (relative paths)
- src/extractor/pipeline/steps/05_table_extractor.py
- src/extractor/pipeline/steps/06_figure_extractor.py
- src/extractor/pipeline/steps/07b_paragraph_polish.py
- src/extractor/pipeline/steps/07c_table_title_infer.py
- src/extractor/pipeline/steps/07d_figure_caption_refine.py
- src/extractor/pipeline/steps/07f_arango_export.py
- src/extractor/pipeline/utils/litellm_call.py

Scenarios (live features of interest)
- Deterministic mode and stable summaries (downstream QA snapshot-diffing).
- LLM-guarded reflow refinements with minimal acceptance checks (alpha-token thresholds, generics blacklists).
- Router warm-up behavior under bounded timeouts; watchdogs preventing silent stalls.

Repository Hygiene
- Branch contains only minimal, targeted diffs; unrelated Ruff warnings exist elsewhere and are intentionally out of scope for this PR.

