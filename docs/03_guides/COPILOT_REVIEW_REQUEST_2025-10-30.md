# Generalized Copilot Request — Patch + Answers (No PRs, No Links)

**AGENT INSTRUCTIONS**
Remember to commit and push the current branch to the repo first
Do NOT IGNORE!!!!!!!


**Project**

* Fork/Repo: `grahama1970/extractor`
* Branch: `main`
* Path: `git@github.com:grahama1970/extractor.git#main`

**Task**

* Harden the extractor pipeline for reliability and failure‑proof operation: enforce Router‑only SciLLM calls, strict JSON everywhere, cross‑platform timeouts, complete router/session shutdown, remove deprecated pandas usage, and fix minor output/observability issues.

**Context (brief, optional)**

* The driver is now fail‑fast (preflight + per‑stage timeouts + stage logs + timings). We removed a duplicate Stage 05 invocation, made Stage 03 mandatory for Stage 04, centralized router usage, trimmed Stage 09 JSON, and upgraded 09a annotator with logs/previews/PDF comments. Remaining reliability items should be addressed via precise diffs.
* Online‑only. Must pin `CHUTES_TEXT_MODEL` and `CHUTES_VLM_MODEL`. No soft‑skips.

**Review Scope (relative paths)**

* Primary:
  * src/extractor/pipeline/steps/07_reflow_section.py
  * src/extractor/pipeline/steps/06b_layout_sketcher.py
  * src/extractor/pipeline/steps/10_arangodb_exporter.py
  * src/extractor/pipeline/utils/scillm_router.py
  * src/extractor/pipeline/run_pipeline.py
* Also check (if needed):
  * docs/PIPELINE_RUNBOOK.md
  * src/extractor/pipeline/steps/06_figure_extractor.py
  * src/extractor/pipeline/steps/09_section_summarizer.py

**Objectives**

* Replace pandas `DataFrame.applymap` in Stage 07 with a vectorized/modern equivalent to remove the FutureWarning; preserve behavior and performance.
* Enforce strict JSON mode on all Stage 07 `.acompletion` call sites; trim unexpected keys and add per‑attempt raw previews to timings on error (match Stage 09 summarizer pattern).
* Ensure global router/session shutdown: rely on `close_all_routers()` at driver end; remove any per‑task router closes that race or leak. Silence aiohttp "Unclosed client session" at process exit.
* Fix Stage 10 final print/log so the output path is one line and matches the actual file.
* Stage 06b: compute timings with a real start time; add stage sink if missing; keep VLM assist opt‑in and pinned.
* Manifest/observability: record per‑stage `served_model` (if available) in timings and ensure `manifest.finalize()` is never shadowed/regressed.
* Docs: update `PIPELINE_RUNBOOK.md` to mention 09a previews, Router‑only policy, and the per‑stage logs/timings.

**Constraints**

* **Unified diff only**, inline inside a single fenced block.
* **No PRs, no hosted links, no URLs, no extra commentary.**
* Include a **one-line commit subject** inside the patch.
* **Numeric hunk headers only** (`@@ -old,+new @@`), no symbolic headers.
* Patch must apply cleanly on branch `main`.
* Preserve plan→execute semantics; avoid destructive defaults.

**Acceptance (we will validate)**

* Running the driver on `data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf` exits 0, prints single‑line Stage 10 output path (when not skipped), and writes per‑stage logs + timings without aiohttp session warnings.
* Stage 07 produces no pandas FutureWarning; all `.acompletion` calls pass `response_format={"type":"json_object"}` and trim extra keys; error previews appear in timings when failures occur.
* `docs/PIPELINE_RUNBOOK.md` documents Router‑only, model pins, and 09a previews.

**Deliverables (STRICT — inline only; exactly these sections, in this order)**

1. **UNIFIED_DIFF:**

```diff
```

2. **ANSWERS:**

* Yes — pin both `CHUTES_TEXT_MODEL` and `CHUTES_VLM_MODEL`; no auto‑discovery.
* Yes — exporters/parsers should tolerate missing columns but smokes must fail on schema mismatches that affect core outputs.
* Yes — all mutating paths remain behind explicit flags; no hidden writes.
* Tests/smokes: strict JSON parsing smokes for 07/09; pipeline run must produce non‑empty timings and manifest; counts > 0 for sections/tables/figures.
* Performance: keep <=3 concurrent LLM calls by default; maintain 300s per‑stage timeout; no retries unless explicitly added.
* Observability: per‑stage "start/ok" lines; write `timings.jsonl`, `timings_summary.json`, and include `served_model`.

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
```

ANSWERS:

* Yes — pin both CHUTES models; no auto‑discovery.
* Tolerate read‑side drift; fail smokes on core schema.
* All writes gated; no hidden mutations.
* Strict JSON smokes + non‑empty timings/manifest.
* ≤3 workers; 300s per‑stage; no implicit retries.
* Print per‑stage start/ok and final manifest/timings paths.
