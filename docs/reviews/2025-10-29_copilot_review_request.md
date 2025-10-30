# Generalized Copilot Request — Patch + Answers (No PRs, No Links)

**AGENT INSTRUCTIONS**
Remember to commit and push the current branch to the repo first
Do NOT IGNORE!!!!!!!

**Project**

* Fork/Repo: grahama1970/extractor
* Branch: main (local working tree)
* Path: git@github.com:grahama1970/extractor.git#main

**Task**

* Harden Stage 06a SciLLM usage (Router/Bearer-only), fix import alias usage for step modules, and add minimal non-bespoke logs/timing. Do not introduce bespoke wrappers or httpx fallbacks.

**Context (brief, optional)**

* Repeated hangs observed while calling 06a title inference. Local evidence suggests import misuse (`_06a_…` vs `s06a_…`) and potential blocking in `get_text_router()` when misconfigured. Tenant requires Bearer for `/chat/completions`; x-api-key 401s.
* We must stay SciLLM-only (Router + acompletion), no litellm/httpx fallbacks, no custom wrappers beyond `utils/scillm_router.py`.

**Review Scope (relative paths)**

* Primary:
  * src/extractor/pipeline/steps/06a_title_caption_enricher.py
  * src/extractor/pipeline/steps/__init__.py
  * src/extractor/pipeline/utils/scillm_router.py
  * src/extractor/pipeline/utils/preflight.py
  * src/extractor/pipeline/utils/response_utils.py
* Also check (if needed):
  * src/extractor/pipeline/steps/07_reflow_section.py (Router close + dict-or-string JSON)
  * scripts/tools/scillm_quick_doctor.py (sanity patterns)

**Objectives**

* Ensure 06a uses `from extractor.pipeline.steps import s06a_title_caption_enricher as step06a` in examples/smokes; avoid `_06a_*` imports.
* Enforce Router/Bearer-only for chat on this tenant; remove any x-api-key chat paths in code paths used by 06a.
* Guarantee timeouts and non-hanging behavior; add measurable `timings.jsonl` rows and `last_request/last_response` artifacts when `RUN_RESULTS_DIR` is set.

**Constraints**

* Unified diff only, inline inside a single fenced block.
* No PRs, no hosted links, no URLs, no extra commentary.
* Include a one-line commit subject inside the patch.
* Numeric hunk headers only (`@@ -old,+new @@`).
* Patch must apply cleanly on branch `main`.
* Preserve SciLLM-only policy; no bespoke HTTP clients.

**Acceptance (we will validate)**

* `python - <<PY` smoke using `s06a_title_caption_enricher._chutes_title_infer_struct("Table 4-1…")` returns a dict or `None` within 30s, without hang.
* When `RUN_RESULTS_DIR=data/results/pipeline`, 06a writes `06a_title_caption_enricher/logs/last_request.json`, `last_response.json`, and appends to `timings.jsonl`.
* No references to litellm/httpx in 06a path; Router auth uses Bearer; import alias `s06a_…` works.

**Deliverables (STRICT — inline only; exactly these sections, in this order)**

1. **UNIFIED_DIFF:**

```diff
<entire unified diff here>
```

2. **ANSWERS:**

* `<Answer to Q1>`
* `<Answer to Q2>`
* `<Answer to Q3>`
* `…`

**Clarifying Questions (answer succinctly in the ANSWERS section; if unknown, reply `TBD` + minimal dependency needed)**

* Dependencies/data sources: Do we need to pin inputs/models/versions for repeatability?
* Schema drift: Should exporters/parsers tolerate missing/renamed columns with failing smokes?
* Safety: Are all mutating paths gated behind `--execute`? Any missing guards?
* Tests/smokes: Which deterministic smokes must pass (counts > 0, strict formats)?
* Performance: Any batch sizes, rate limits, or timeouts/retries to honor?
* Observability: What summary lines should the CLI print on completion?

**Output Format (must match exactly; no extra text):**
UNIFIED_DIFF:

```diff
<entire unified diff here>
```

ANSWERS:

* `<bullet answers in order of the clarifying questions>`
