# Generalized Copilot Request — Patch + Answers (No PRs, No Links)

**AGENT INSTRUCTIONS**
Remember to commit and push the current branch to the repo first
Do NOT IGNORE!!!!!!!


**Project**

* Fork/Repo: "grahama1970/extractor"
* Branch: "feat/annotator-pymupdf-restore"
* Path: "git@github.com:grahama1970/extractor.git#feat/annotator-pymupdf-restore"

**Task**

* Consolidate SciLLM-only async calls, remove litellm/shims, normalize JSON-mode parsing, add array-safe xtrace runner, and enforce PDF annotation safety.

**Context (brief, optional)**

* Migrated to SciLLM; residual litellm/shims and inconsistent JSON-mode handling cause brittleness (e.g., Stage 07 "empty content" when content is a dict). Prior "hangs" were shell early-exit due to quoting.
* Operate with SciLLM acompletion only (no httpx fallbacks); never mutate PDFs under data/input/.

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
  * src/extractor/pipeline/utils/litellm_call.py
  * src/extractor/pipeline/utils/litellm_cache.py
  * src/extractor/pipeline/utils/litellm_image_utils.py
  * src/extractor/pipeline/utils/litellm_response_utils.py
  * src/extractor/pipeline/utils/chutes_client.py
  * src/extractor/pipeline/utils/scillm_client.py
  * src/extractor/pipeline/utils/vendor_parallel_acompletion.py
  * scripts/run_simple.sh
  * scripts/tools/remove_pdf_annotations.py
  * AGENTS.md, SCILLM_USAGE.md, README.md

**Objectives**

* Remove litellm shims/imports; use scillm.acompletion everywhere (no httpx).
* Normalize JSON-mode to accept dict or string in choices[0].message.content.
* Remove bespoke SciLLM wrappers; call SciLLM directly.
* Add array-safe scripts/tools/pipeline_xtrace.sh with per-stage .out/.err + JSON summary.
* Enforce: never mutate PDFs under data/input/; operate on copies only.

**Constraints**

* **Unified diff only**, inline inside a single fenced block.
* **No PRs, no hosted links, no URLs, no extra commentary.**
* Include a **one-line commit subject** inside the patch.
* **Numeric hunk headers only** (`@@ -old,+new @@`), no symbolic headers.
* Patch must apply cleanly on branch "feat/annotator-pymupdf-restore".
* Preserve plan→execute semantics; avoid destructive defaults.

**Acceptance (we will validate)**

* rg -n "litellm_call|chutes_scillm|achutes_chat|httpx" under src/extractor/ → none (tests allowed).
* Stage 07 writes non-empty strict JSON; no "empty content" errors when content is dict.
* scripts/tools/pipeline_xtrace.sh produces per-stage logs and a JSON summary; no shell quoting failures.

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

* Dependencies/data sources: Do we need to pin inputs/models/versions for repeatability?
* Schema drift: Should exporters/parsers tolerate missing/renamed columns with failing smokes?
* Safety: Are all mutating paths gated behind `--execute`? Any missing guards?
* Tests/smokes: Which deterministic smokes must pass (counts > 0, report count==pairs, strict formats)?
* Performance: Any batch sizes, rate limits, or timeouts/retries to honor?
* Observability: What summary lines should the CLI print on completion?

**Output Format (must match exactly; no extra text):**
UNIFIED_DIFF:

```diff
<entire unified diff here>
```

ANSWERS:

* <bullet answers in order of the clarifying questions>
