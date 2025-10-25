# Generalized Copilot Request — Patch + Answers (No PRs, No Links)

**AGENT INSTRUCTIONS**
Remember to commit and push the current branch to the repo first
Do NOT IGNORE!!!!!!!


**Project**

* Fork/Repo: `grahama1970/extractor`
* Branch: `feat/annotator-pymupdf-restore`
* Path: `git@github.com:grahama1970/extractor.git#feat/annotator-pymupdf-restore`

**Task**

* Stabilize pipeline steps 01→07 under a SciLLM‑only policy; enforce text‑only for Stage 07; normalize JSON‑mode parsing (dict or string) at a single choke‑point; remove deprecated litellm/httpx paths on the hot path; add an array‑safe xtrace runner; deliver one unified diff.

**Context (brief, optional)**

* Failures stem from JSON‑mode shape (content as dict vs string) and legacy paths. Stage 07 must be text‑only (reflow text + merge tables). Inputs must never mutate PDFs under `data/input/`. Add a small array‑safe runner to capture per‑stage logs to avoid “hangs”.

**Review Scope (relative paths)**

* Primary:

  * `src/extractor/pipeline/steps/01_annotation_processor.py`
  * `src/extractor/pipeline/steps/02_marker_extractor.py`
  * `src/extractor/pipeline/steps/04_section_builder.py`
  * `src/extractor/pipeline/steps/05_table_extractor.py`
  * `src/extractor/pipeline/steps/06_figure_extractor.py`
  * `src/extractor/pipeline/steps/06a_title_caption_enricher.py`
  * `src/extractor/pipeline/steps/06b_layout_sketcher.py`
  * `src/extractor/pipeline/steps/07_reflow_section.py`
* Also check (if needed):

  * `src/llm_adapter/adapter.py`
  * `src/extractor/pipeline/utils/response_utils.py`
  * `src/extractor/pipeline/utils/llm_utils.py`
  * `src/extractor/pipeline/utils/preflight.py`
  * `src/extractor/pipeline/utils/model_select.py`
  * `src/extractor/pipeline/utils/litellm_response_utils.py` (target for removal/replace)
  * `scripts/tools/pipeline_xtrace.sh` (new)
  * `scripts/run_simple.sh`
  * `scripts/tools/remove_pdf_annotations.py`
  * Docs/README references if touched

**Objectives**

* JSON‑mode normalization: single helper that accepts dict‑or‑string in `choices[0].message.content`; use it in the adapter and Stage 07.
* Stage 07 text‑only: remove/disable multimodal branches; always select `CHUTES_TEXT_MODEL`; keep focus on reflow text + merge tables.
* SciLLM‑only: replace any litellm/httpx paths on the 01→07 flow; call `scillm.acompletion` (async) consistently.
* Xtrace runner: ensure `scripts/tools/pipeline_xtrace.sh` exists (array‑safe), captures per‑stage `stage.out`/`stage.err`, and writes `summary.json`.
* Safety: never mutate PDFs under `data/input/`; rely on `scripts/tools/remove_pdf_annotations.py` to produce copies.

**Constraints**

* **Unified diff only**, inline inside a single fenced block.
* **No PRs, no hosted links, no URLs, no extra commentary.**
* Include a **one‑line commit subject** inside the patch.
* **Numeric hunk headers only** (`@@ -old,+new @@`), no symbolic headers.
* Patch must apply cleanly on branch `feat/annotator-pymupdf-restore`.
* Preserve plan→execute semantics; avoid destructive defaults.

**Acceptance (we will validate)**

* Ripgrep guardrails:
  * `rg -n "litellm_response_utils|httpx.get\(|openai_like" src/extractor` → no matches
  * `rg -n "include_images" src/extractor/pipeline/steps/07_reflow_section.py` → only in comments/disabled logic
* JSON normalization:
  * Adapter + Stage 07 accept dict‑or‑string JSON content; no “empty content” paths remain.
* Runner present:
  * `scripts/tools/pipeline_xtrace.sh` is executable and produces a `summary.json` with populated stages.
* Safety:
  * No writes to `data/input/`; Stage 01 and tools operate on copies.

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

* Dependencies/data sources: Pin `CHUTES_TEXT_MODEL`/`CHUTES_VLM_MODEL` via env only, or add defaults in `model_select.py`?
* Schema drift: Should parsers tolerate missing/renamed JSON keys with warnings, or fail fast?
* Safety: Enforce a hard guard to prevent writes under `data/input/` at all CLI entrypoints?
* Tests/smokes: Which deterministic smokes must pass locally (e.g., JSON present, counts > 0)? Any CI‑only checks?
* Performance: Preferred default acompletion timeout and concurrency for 01→07 (e.g., 60–90s, ≤8 workers)?
* Observability: Minimal summary lines/counters each stage should print (counts, artifact paths)?

**Output Format (must match exactly; no extra text):**
UNIFIED_DIFF:

```diff
<entire unified diff here>
```

ANSWERS:

* `<bullet answers in order of the clarifying questions>`

---

## Quick “Drop-In” Mini Version

**Request:** Produce a **single unified diff** (inline) for `grahama1970/extractor#feat/annotator-pymupdf-restore` that stabilizes 01→07 (SciLLM‑only; Stage 07 text‑only; JSON‑mode normalization; drop litellm/httpx on hot path; add xtrace runner).
**Scope:** `src/extractor/pipeline/steps/0{1,2,4,5,6,6a,6b,7}_*.py`, `src/llm_adapter/adapter.py`, `src/extractor/pipeline/utils/{response_utils.py,llm_utils.py,preflight.py,model_select.py}`, `scripts/tools/pipeline_xtrace.sh`
**Constraints:** No PRs/links; include a one‑line commit subject; numeric hunks only; patch applies cleanly.
**Acceptance:** rg guards above; xtrace runner present; Stage 07 JSON accepted dict or string; no writes to `data/input/`.

**Output (exact):**
UNIFIED_DIFF:

```diff
<entire unified diff here>
```

ANSWERS:

* `<answers to: deps, schema drift, safety, tests, performance, observability>`
