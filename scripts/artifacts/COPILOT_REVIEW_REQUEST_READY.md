# Generalized Copilot Request — Patch + Answers (No PRs, No Links)

**AGENT INSTRUCTIONS**
Remember to commit and push the current branch to the repo first
Do NOT IGNORE!!!!!!!


**Project**

* Fork/Repo: "grahama1970/extractor"
* Branch: "feat/annotator-pymupdf-restore"
* Path: "git@github.com:grahama1970/extractor.git#feat/annotator-pymupdf-restore"

**Task**

* Structured code review of the extractor pipeline for robustness and maintainability under a "SciLLM-only, async-only" policy; propose minimal, high-confidence changes via a single unified diff (no re-architecture).

**Context (brief, optional)**

* The project has moved to SciLLM (Chutes) calls only and aims to remove legacy litellm usage. JSON mode responses may be dict or string; code should normalize once. Avoid bespoke wrappers; ensure pipeline never mutates PDFs under `data/input/`.

**Review Scope (relative paths)**

* Primary:

  * src/extractor/pipeline/steps/01_annotation_processor.py
  * src/extractor/pipeline/steps/03_suspicious_headers.py
  * src/extractor/pipeline/steps/05_table_extractor.py
  * src/extractor/pipeline/steps/06_figure_extractor.py
  * src/extractor/pipeline/steps/06a_title_caption_enricher.py
  * src/extractor/pipeline/steps/06b_layout_sketcher.py
  * src/extractor/pipeline/steps/07_reflow_section.py
  * src/extractor/pipeline/steps/08_lean4_theorem_prover.py
  * src/extractor/pipeline/steps/09_section_summarizer.py
  * src/extractor/pipeline/steps/11_arango_create_graph.py
* Also check (if needed):

  * src/llm_adapter/adapter.py
  * src/extractor/pipeline/utils/llm_utils.py
  * src/extractor/pipeline/utils/litellm_response_utils.py
  * src/extractor/pipeline/utils/litellm_call.py (target for removal)
  * src/extractor/pipeline/utils/vendor_parallel_acompletion.py
  * src/extractor/pipeline/utils/chutes_client.py
  * src/extractor/pipeline/utils/scillm_client.py
  * src/extractor/pipeline/utils/model_select.py
  * src/extractor/pipeline/utils/preflight.py
  * scripts/run_simple.sh
  * scripts/tools/remove_pdf_annotations.py
  * AGENTS.md, SCILLM_USAGE.md, README.md

**Objectives**

* Identify and remove remaining litellm/shim usages; rely on `scillm.acompletion` consistently (no httpx fallbacks).
* Normalize JSON mode parsing once (dict or string in `choices[0].message.content`) and use it across call sites.
* Eliminate ad‑hoc/bespoke SciLLM wrappers; prefer direct, consistent calls.
* Add a simple array‑safe xtrace runner script (`scripts/tools/pipeline_xtrace.sh`) to capture per‑stage `.out/.err` and a JSON summary (optional but preferred if small/safe).
* Enforce that PDFs under `data/input/` are never mutated in place.

**Constraints**

* **Unified diff only**, inline inside a single fenced block.
* **No PRs, no hosted links, no URLs, no extra commentary.**
* Include a **one-line commit subject** inside the patch.
* **Numeric hunk headers only** (`@@ -old,+new @@`), no symbolic headers.
* Patch must apply cleanly on branch "feat/annotator-pymupdf-restore".
* Prefer minimal, high-confidence edits; avoid large refactors.

**Acceptance (we will validate)**

* `rg -n "litellm_call|litellm_cache|httpx" src/extractor` returns none (tests allowed).
* A JSON content normalizer is introduced/used in adapter/07 to handle dict-or-string uniformly; Stage 07 no longer errors on "empty content".
* Optional xtrace script exists and produces per‑stage logs and a summary JSON without quoting errors.
* No code path mutates PDFs under `data/input/`.

**Deliverables (STRICT — inline only; exactly these sections, in this order)**

1. **UNIFIED_DIFF:**

```diff
<entire unified diff here>
```

2. **ANSWERS:**

* <Answer to deps/models pinning>
* <Answer to schema drift tolerance>
* <Answer to safety/guards>
* <Answer to tests/smokes>
* <Answer to performance/timeouts/concurrency>
* <Answer to observability/summary lines>

**Clarifying Questions (answer succinctly in the ANSWERS section; if unknown, reply `TBD` + minimal dependency needed)**

* Dependencies/data sources: Should inputs/models be pinned for repeatability?
* Schema drift: Tolerate missing/renamed keys with warnings or fail fast?
* Safety: Is a global guard desired to prevent writes under `data/input/`?
* Tests/smokes: Which deterministic smokes must pass locally?
* Performance: Preferred default concurrency/timeouts for `scillm.acompletion`?

**Output Format (must match exactly; no extra text):**
UNIFIED_DIFF:

```diff
<entire unified diff here>
```

ANSWERS:

* <bullet answers in order of the clarifying questions>
