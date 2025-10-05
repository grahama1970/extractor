Fork: grahama1970/extractor
Branch: feat/step07-iteration3-diffs
Path: git@github.com:grahama1970/extractor.git#feat/step07-iteration3-diffs

Title: Stage‑07 micro‑pipeline + Warm‑Start/Timeout Hardening — Request for Comprehensive Review

Context
- This PR series hardens Stage‑07 (canonicalize → polish → titles → captions → assemble) and adds enrichment (07g–07n). It also addresses warm‑start latency and router timeouts for Chutes via LiteLLM.
- Live features: continuity merges, paragraph polish, table title inference, caption refine, reflow assembly, cross‑refs, requirements, entities, equations, confidence, deltas, pipeline summary, budget ledger.

Key changes to review (relative paths)
- Router/LLM: src/extractor/pipeline/utils/litellm_call.py (timeout/backoff, Retry‑After, warm_start_metrics)
- Budget: src/extractor/pipeline/utils/budget.py; 07b/07c/07d integration
- Anchors/Hashes: src/extractor/pipeline/steps/07a_section_canonicalizer.py; 07e_assemble_reflow.py
- Gated stages: 07b_paragraph_polish.py, 07c_table_title_infer.py, 07d_figure_caption_refine.py (validators, model_used, prompt_version)
- Enrichment: 07g_cross_reference_resolver.py, 07h_requirement_classifier.py, 07i_entity_extractor.py, 07j_equation_extractor.py, 07k_table_span_refiner.py, 07l_confidence_scorer.py, 07m_version_diff.py, 07n_pipeline_mode_summary.py
- Arango: 07f_arango_export.py (STRICT_KEY_NAMESPACE dev check + semantic upserts)
- Invalidation: docs/pipeline_invalidation_matrix.md

Warm‑start specifics
- Honor Retry‑After on 429; otherwise 1.0s→2.0s backoff; classify PROVIDER_429.
- Router timeout applied; request‑level timeouts remain per stage.
- Optional warm_start_metrics.json under data/results/pipeline/metrics/ (ENABLE_WARM_START_METRICS=1).

Acceptance
- No hangs on cold start; Router timeouts honored; 429 behavior correct.
- Budget ledger pauses when predicted tokens exceed LLM_DAILY_TOKEN_BUDGET (dry‑run supported).
- Anchors stable; deltas include prev/new snippets; requirement formal_status present.

Clarifying questions for Copilot
1) litellm_call: Is our Router(timeout, retry_after) placement and per‑request timeout usage correct across streaming and non‑streaming? Suggest minimal diffs if not.
2) 429 handling: Should we consider jitter (±200ms) on backoff before final fail? Provide tiny patch if recommended.
3) Warm metrics: Any race or overhead concerns writing the latest‑only JSON in finally? Propose a small batching or debounce if needed.
4) Validators (07b/07c/07d): Any simpler acceptance rule that reduces false positives while preventing drift? Provide exact one‑liners.
5) Arango STRICT_KEY_NAMESPACE: Is the _key prefix guard adequate? Suggest additional collection/key checks.
6) Invalidation matrix: Any edge we missed (e.g., 07k tiers impacting 07e consumers)?

Please respond with answers and minimal unified diffs where changes are suggested.

