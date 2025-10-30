# Generalized Copilot Request — Patch + Answers (No PRs, No Links)

**AGENT INSTRUCTIONS**
Remember to commit and push the current branch to the repo first
Do NOT IGNORE!!!!!!!


**Project**

* Fork/Repo: `grahama1970/extractor`
* Branch: `feat/remove-step-clis-20251026`
* Path: `git@github.com:grahama1970/extractor.git#feat/remove-step-clis-20251026`

**Task**

* Harden Stage 09 summarization to Router-only strict JSON (no fallbacks), close sessions cleanly, and standardize logs per SciLLM protocol.

**Context (brief, optional)**

* The sequential pipeline ran twice on Oct 29, 2025 with .env loaded inline. Stages 01–08 and 10 complete deterministically. Stage 09 previously produced fallback summaries; it has now been switched to Router-only strict JSON and succeeded. We want Copilot to review the implementation and propose any surgical improvements while keeping policy alignment.
* SciLLM policy: Router-only (scillm.Router(.acompletion)), strict JSON, temp=0, centralized client (no bespoke adapters), Bearer for chat on this tenant. Preflight probes and per-attempt timings files are expected but not all are in place.

Results Summary (artifacts for analysis)
- Run A (fail-fast variant): `local/results/pipeline/dev_20251029_155752_ff`
  - Manifest counts: blocks02=53, sections04=7, tables05=9, figures06=1
  - Stage 09: 7 sections processed; 8 outputs (7 section summaries + 1 checkpoint); success=true for all
  - Key concepts per section: avg=6.5, min=5, max=7
  - Sample titles: “4.1.5.4. BHT (Branch History Table) submodule”, “4.1.5.4.1. REQUIREMENTS (Simulated)”
  - Noted warnings: Unclosed client session/connector at process end
  - Key files:
    - `local/results/pipeline/dev_20251029_155752_ff/manifest.json`
    - `local/results/pipeline/dev_20251029_155752_ff/09_section_summarizer/json_output/09_summaries.json`
    - `local/results/pipeline/dev_20251029_155752_ff/07_reflow_section/json_output/07_reflowed.json`
- Run B (prior run): `local/results/pipeline/dev_20251029_154729`
  - Manifest counts: blocks02=53, sections04=7, tables05=9, figures06=1
  - Stage 09 previously produced 0/7 success; served here for comparison
  - Key file: `local/results/pipeline/dev_20251029_154729/09_section_summarizer/json_output/09_summaries.json`

Implementation touched
- `src/extractor/pipeline/steps/09_section_summarizer.py`: Router-only strict JSON; removed bespoke fallbacks; added router close.

**Review Scope (relative paths)**

* Primary:

  * `src/extractor/pipeline/steps/09_section_summarizer.py`
  * `src/extractor/pipeline/utils/scillm_router.py`
  * `src/extractor/pipeline/run_pipeline.py`
* Also check (if needed):

  * `scripts/tools/scillm_quick_doctor.py`
  * `src/extractor/pipeline/utils/chutes_text.py`
  * `src/extractor/pipeline/utils/response_utils.py`
  * `src/extractor/pipeline/utils/json_mode.py`

**Objectives**

* Enforce Router-only calls for Stage 09; remove SDK/curl/adapters from Stage 09.
* Fail fast on any non-strict JSON; no deterministic text fallbacks.
* Ensure sessions/routers close cleanly to eliminate aiohttp warnings.
* Add per-attempt timings: write `timings.jsonl` and `timings_summary.json` for Stage 09 calls (served_model, tokens, latency_ms, outcome).
* Keep patches minimal and consistent with repo conventions.

**Constraints**

* **Unified diff only**, inline inside a single fenced block.
* **No PRs, no hosted links, no URLs, no extra commentary.**
* Include a **one-line commit subject** inside the patch.
* **Numeric hunk headers only** (`@@ -old,+new @@`), no symbolic headers.
* Patch must apply cleanly on branch `feat/remove-step-clis-20251026`.
* Preserve plan→execute semantics; avoid destructive defaults.

**Acceptance (we will validate)**

* Re-run pipeline with the same input; Stage 09 either produces strict-JSON summaries or raises immediately on first deviation (no fallbacks).
* No “Unclosed client session/connector” warnings on process exit.
* Stage 09 writes per-attempt `timings.jsonl` and aggregate `timings_summary.json` under `local/results/pipeline/<run>/09_section_summarizer/`.
* No changes to Stage counts for 01–06; Stage 09 retains 7 section summaries plus one checkpoint.

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

**Request:** Produce a **single unified diff** (inline) for `grahama1970/extractor#feat/remove-step-clis-20251026` that achieves: Router-only strict JSON Stage 09, fail-fast, session cleanup, per-attempt timings.
**Scope:** `src/extractor/pipeline/steps/09_section_summarizer.py`, `src/extractor/pipeline/utils/scillm_router.py`
**Constraints:** No PRs/links; include a one-line commit subject; numeric hunk headers only; patch applies cleanly.
**Acceptance:** Strict JSON enforced, no fallbacks, no unclosed-session warnings, timings files present.

**Output (exact):**
UNIFIED_DIFF:

```diff
<entire unified diff here>
```

ANSWERS:

* `<answers to: deps, schema drift, safety, tests, performance, observability>`

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

