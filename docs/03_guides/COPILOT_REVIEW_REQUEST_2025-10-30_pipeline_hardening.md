# Generalized Copilot Request — Patch + Answers (No PRs, No Links)

**Project**

* Fork/Repo: `grahama1970/extractor`
* Branch: `main`
* Path: `git@github.com:grahama1970/extractor.git#main`

**Task**

* Harden SciLLM integration and pipeline shutdown to fully eliminate aiohttp client warnings, enforce Router-only usage, and tighten JSON-mode reliability across Stages 06/06b/07/09.

**Context (brief, optional)**

* The pipeline now runs online-only with pinned `CHUTES_TEXT_MODEL`/`CHUTES_VLM_MODEL`, per-stage timeouts, per-stage file sinks, and timings in the manifest. We removed duplicate Stage 05 and fixed `--stop-on-fail`. We added a best-effort router shutdown at the end of the driver.
* Residual issue: after a successful run, we still see a benign but noisy warning: `Unclosed client session/connector` from aiohttp. The scillm agent indicates we should call `scillm.shutdown()` (alias `shutdown_clients()`). Our environment’s `scillm` currently lacks that attribute; we fall back to `close_all_routers()`.
* Goal: make shutdown noise go to zero, keep Router-only guarantees, and further harden strict JSON handling.

**Review Scope (relative paths)**

* Primary:

  * `src/extractor/pipeline/run_pipeline.py`
  * `src/extractor/pipeline/utils/scillm_router.py`
  * `src/extractor/pipeline/steps/07_reflow_section.py`
  * `src/extractor/pipeline/steps/06_figure_extractor.py`
  * `src/extractor/pipeline/steps/06b_layout_sketcher.py`
  * `src/extractor/pipeline/steps/09_section_summarizer.py`
  * `src/extractor/pipeline/steps/scillm_preflight_validator.py`
* Also check (if needed):

  * Any remaining steps under `src/extractor/pipeline/steps/` that might instantiate aiohttp/httpx sessions directly or bypass `utils/scillm_router.py`.

**Objectives**

* Eliminate all residual "Unclosed client session/connector" warnings on pipeline exit.
* Keep Router-only policy: no local liteLLM/SDK clients in steps; everything flows through `utils/scillm_router.py`.
* Tighten strict JSON handling: Stage 07/09 must trim top-level keys, log served_model/tokens/latency, and fail closed on invalid JSON.
* Ensure preflight rides out transient 5xx via paved helpers first, with minimal fallback retries.

**Constraints**

* **Unified diff only**, inline inside a single fenced block.
* **No PRs, no hosted links, no URLs, no extra commentary.**
* Include a **one-line commit subject** inside the patch.
* **Numeric hunk headers only** (`@@ -old,+new @@`), no symbolic headers.
* Patch must apply cleanly on branch `main`.
* Preserve plan→execute semantics; avoid destructive defaults.

**Acceptance (we will validate)**

* Run: `python -m extractor.pipeline --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf --out data/results/pipeline/review_run --stop-on-fail --skip-export` exits 0.
* No `Unclosed client session` or `Unclosed connector` lines in stderr.
* `data/results/pipeline/review_run/timings_summary.json` includes a non-empty `served_model`, and Stage 07 timings show attempts with latency/tokens.
* `data/results/pipeline/review_run/07_reflow_section/json_output/07_reflowed.json` has expected top-level keys only after trimming.

**Deliverables (STRICT — inline only; exactly these sections, in this order)**

1. **UNIFIED_DIFF:**

```diff
<entire unified diff here>
```

2. **ANSWERS:**

* Yes — pin both CHUTES models; no auto-discovery.
* Tolerate read-side drift with explicit, failing smokes on core schema keys; no silent fallbacks.
* All mutating/export paths remain behind explicit flags (e.g., `--skip-export`); no hidden writes.
* Deterministic JSON smokes for Stage 07/09 and non-empty timings/manifest are required.
* ≤3 workers; 300s per-stage; paved transient retries only (no bespoke exponential layering in steps).
* CLI must print per-stage start/ok lines and the final manifest/timings paths.

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

* `<bullet answers in order of the clarifying questions>`
