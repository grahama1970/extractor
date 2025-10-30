# Generalized Copilot Request — Patch + Answers (No PRs, No Links)

**AGENT INSTRUCTIONS**
Remember to commit and push the current branch to the repo first
Do NOT IGNORE!!!!!!!


**Project**

* Fork/Repo: `grahama1970/extractor`
* Branch: `feat/remove-step-clis-20251026`
* Path: `git@github.com:grahama1970/extractor.git#feat/remove-step-clis-20251026`

**Task**

* Comprehensive reliability hardening and failure-point cleanup for the PDF pipeline driver and stages (online-only, SciLLM/Chutes pinned), with fail-fast behavior and reproducible observability.

**Context (brief, optional)**

* The pipeline must run online-only using Chutes via the centralized SciLLM router. Soft-skips and offline fallbacks are not allowed. Prior runs exposed fragility: duplicated stage invocation, manifest shadowing preventing finalize, confusing stop-on-fail flag behavior, mixed router usage, duplicate helper names, sporadic session leaks, and inconsistent logging.
* Desired outcome: a deterministic, fail-fast pipeline that cleanly aborts on missing upstream artifacts, enforces SciLLM preflight, uses a centralized router, and emits actionable logs and timings per stage without aiohttp session warnings.

**Review Scope (relative paths)**

* Primary:

  * `src/extractor/pipeline/run_pipeline.py`
  * `src/extractor/pipeline/steps/`
  * `src/extractor/pipeline/utils/scillm_router.py`
  * `docs/PIPELINE_RUNBOOK.md`
* Also check (if needed):

  * `src/extractor/pipeline/steps/06_figure_extractor.py`
  * `src/extractor/pipeline/steps/07_reflow_section.py`
  * `src/extractor/pipeline/steps/09a_pdf_annotator.py`
  * `src/extractor/pipeline/steps/10_arangodb_exporter.py`
  * `src/extractor/pipeline/utils/`

**Objectives**

* Fix driver sequencing: Stage 05 must run exactly once, consuming Stage 04 outputs; remove any duplicate invocations.
* Unshadow manifest: ensure `RunManifest.finalize()` always runs; remove dict shadowing; record served_model and per-stage latency.
* Correct CLI flags: `--stop-on-fail` should default to `False` (opt-in); add `--stage-timeout` with cross-platform fallback; fail fast on timeouts.
* Enforce Stage dependencies: Stage 03 is mandatory; Stage 04 must hard-fail if Stage 03 outputs are missing required keys; no legacy heuristics fallback.
* Centralize SciLLM usage: all LLM/VLM calls must use `utils/scillm_router.py` (Router-only); remove local LiteLLM/router instantiations.
* Resolve duplicate helpers: eliminate duplicate `_build_compact_prompt` definitions in Stage 07; keep a single, tested implementation.
* Remove soft-skips: Stage 06 descriptions must run whenever not explicitly `--skip-descriptions`; no feature flags that silently disable online calls.
* Close sessions cleanly: ensure routers/clients are closed (`aclose`/`close`) to prevent "Unclosed client session" warnings.
* Strengthen JSON mode: strict `response_format={"type":"json_object"}`; normalize string vs dict; handle arrays and invalid JSON robustly.
* Logging and observability: add per-stage file sinks (including 09a); emit end-of-stage summaries and `timings.jsonl` + `timings_summary.json`; consistent artifact paths.
* Docs: update runbook to Online-Only with explicit `CHUTES_TEXT_MODEL`/`CHUTES_VLM_MODEL` pins; remove offline guidance.

**Constraints**

* **Unified diff only**, inline inside a single fenced block.
* **No PRs, no hosted links, no URLs, no extra commentary.**
* Include a **one-line commit subject** inside the patch.
* **Numeric hunk headers only** (`@@ -old,+new @@`), no symbolic headers.
* Patch must apply cleanly on branch `feat/remove-step-clis-20251026`.
* Preserve plan→execute semantics; avoid destructive defaults.

**Acceptance (we will validate)**

* The driver runs stages in order 01→02→03→04→05→06→07→09 (→10 optional) with no duplicate Stage 05 invocation; Stage 03 absence triggers a hard failure in Stage 04 with a clear log.
* `--stop-on-fail` defaults to off; enabling it aborts immediately on the first stage error; `--stage-timeout` enforces a per-stage ceiling on Linux and a portable fallback on non-POSIX.
* All LLM/VLM calls flow through the centralized SciLLM router; Stage 07 contains exactly one `_build_compact_prompt` helper; no aiohttp session leaks on repeated runs.
* Stage 06 always attempts descriptions when not `--skip-descriptions`; preflight is enforced; no soft flags suppress online calls.
* Manifest `finalize()` runs and includes served_model and per-stage latencies; `timings.jsonl` and `timings_summary.json` are written with non-empty entries.
* 09a annotator has a stage-specific file sink and produces expected annotated artifacts without client errors; exporter prints a single, correct confirmation path.
* Docs reflect Online-Only mode with explicit Chutes model pins; no offline guidance remains.

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

---

## Quick “Drop-In” Mini Version

**Request:** Produce a **single unified diff** (inline) for `grahama1970/extractor#feat/remove-step-clis-20251026` that achieves: reliability hardening (fail-fast, SciLLM-only, no duplicates), manifest finalize, strict JSON, session cleanup, and consistent logging + timings.
**Scope:** `src/extractor/pipeline/run_pipeline.py`, `src/extractor/pipeline/steps/*`, `src/extractor/pipeline/utils/scillm_router.py`, `docs/PIPELINE_RUNBOOK.md`
**Constraints:** No PRs/links; include a one-line commit subject; numeric hunk headers only; patch applies cleanly.
**Acceptance:** Driver sequence fixed; Stage 03 required; centralized router; no aiohttp warnings; timings and manifest updated; Online-Only docs.

**Output (exact):**
UNIFIED_DIFF:

```diff
<entire unified diff here>
```

ANSWERS:

* `Yes — pin CHUTES_TEXT_MODEL and CHUTES_VLM_MODEL; no auto-discovery.`
* `Hard-fail in Stage 04 if Stage 03 output keys are missing; no legacy heuristics fallback.`
* `All mutating/export paths remain behind explicit flags; no hidden writes.`
* `CI must pass strict JSON parsing smokes and non-empty timings/manifest checks.`
* `Stage-timeout default 180s; ≤3 workers; exponential backoff once for provider errors.`
* `CLI prints per-stage summary lines and a final manifest/timings path.`

---

## Optional Toggles (copy/paste as needed)

* **Strict JSON Mode:** “All generated configs/snippets must be strict JSON: no comments, no trailing commas, no markdown/codefences inside the JSON.”
* **Flag-First DX:** “Commands and code must use explicit flag-first configuration; no hidden env defaults.”
* **Worker/Batching Defaults:** “Default ≤3 workers; batch size 10–15; retries with exponential backoff.”
* **Determinism:** “Seeded or deterministic outputs where feasible; produce minified JSON artifacts.”
* **MBOX Variant (if you ever switch modes):** Replace the UNIFIED_DIFF block with:
  **Output (exact):**
  `MBOX:` *(paste full git-format patch series; no code fences)*

---

### Placeholder Key

* `<OWNER/REPO>`: Repository identifier
* `<BRANCH>`: Target branch name
* `<GIT_SOURCE_WITH_BRANCH>`: Fetchable ref (SSH/HTTPS) with `#<BRANCH>` if helpful to your tools
* `<paths…>`: Narrow file list to focus Copilot
* `<brief objectives>` / `<Acceptance>`: What “done” looks like

