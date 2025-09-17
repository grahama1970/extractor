No clarifying questions — I’ll give you a complete, checkbox-driven task list the agent can follow.

---

# Pivot Plan: Agent-Safe Delivery Checklist

**Context:** We’re pivoting from “vibe-coding” to a **contracts + smokes** workflow.
The agent’s scope is constrained to prompts, rule tables, and LLM adapters; the deterministic pipeline remains human-owned/read-only. All progress must be demonstrated by **green smokes + contract tests + goldens**.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## 0) Project Guardrails (once)

* [ ] Create `CONTRIBUTING_AGENT.md` (contribution lane + boundaries)

  * [ ] Allowed: prompts/, rules/, adapter configs, tests
  * [ ] Disallowed: DB schema, stage core logic, infra
  * [ ] Require passing: **smokes + contracts + goldens**
* [ ] Add “protected paths” in CI (block agent edits outside allowed dirs)
* [ ] Add **cost/time** ceilings for agent runs (env: `MAX_CALLS`, `MAX_COST_USD`)
* [ ] Add `scripts/ci_redact.py` to scrub secrets from logs

---

## 1) Environment & Preflight

* [ ] Make target `smoke-env` (PyMuPDF, OpenCV, Camelot, Ghostscript, write perms)
* [ ] Add `requirements-dev.txt` + lockfile; document OS packages (gs, poppler if used)
* [ ] Ensure `.env.example` with all required keys (GEMINI/OPENAI/ARANGO/…)
* [ ] Create a tiny **fixtures set** under `tests/data/`:

  * [ ] `one_annot.pdf` (1 FreeText near a region)
  * [ ] `table_simple.pdf` (1 simple lattice table)
  * [ ] `headers_mixed.pdf` (some fake “suspicious” headers)
  * [ ] `figures_basic.pdf` (1 image + caption)

---

## 2) Test Pyramid Scaffolding

* [ ] **Smokes** (make + pytest harness)

  * [ ] Add `Makefile` targets (from prior message) under `scripts/smoke.sh` as well
  * [ ] `tests/smoke/test_pipeline_smokes.py` minimal asserts per stage
* [ ] **Contract Tests** (schema level)

  * [ ] Add `contracts.py` with Pydantic models for each LLM output:

    * [ ] Stage-01 interpretation schema
    * [ ] Stage-03 header verification schema
    * [ ] Stage-07 reflow JSON schema (`reflowed_json` shape)
    * [ ] Stage-09 summary schema
  * [ ] Tests that invalid/missing/extra keys hard-fail
* [ ] **Goldens** (content level)

  * [ ] Create `tests/golden/` with \~5–20 micro PDFs + expected JSON
  * [ ] Add ratchet test (`pytest -k golden`): updates require reviewer note
* [ ] **Scenario Tests** (fast pipeline slices)

  * [ ] Smoke subsets (01→02→04; 04→05; 04→06; 04+05+06→07 text-only)

---

## 3) LLM Adapter Firebreak

* [ ] Add `llm_adapter/adapter.py`

  * [ ] Single entrypoints:

    * [ ] `verify_header(image_b64, context) -> HeaderVerdict`
    * [ ] `reflow_section(messages, images=[]) -> ReflowedSection`
    * [ ] `summarize_section(text) -> SectionSummary`
  * [ ] Force `response_format={"type":"json_object"}` where supported
  * [ ] Timeouts, retries, **strict schema validation**, minimal JSON “repair” (fence trim only)
  * [ ] Per-call artifact dump: `logs/{stage}/{id}/req.json`, `raw.txt`, `parsed.json`, `verdict.json`
  * [ ] Redaction of secrets; truncate context lengths (env caps)
* [ ] Wire stages to call adapter (but keep current code path behind a flag until green)

---

## 4) Prompts as Code

* [ ] Create `prompts/` tree:

  * [ ] `03_header/system.md`, `03_header/user_guard.md`
  * [ ] `07_reflow/system.md`, `07_reflow/guard_compact.md`
  * [ ] `09_summary/system.md`
* [ ] Add prompt **linter** `tools/prompt_lint.py`

  * [ ] Enforce: “Return ONLY JSON…”, token budget comment, banned hedges
* [ ] Echo prompt version inside each response (e.g., `meta.prompt_version`)

---

## 5) Rule Tables (tunable by agent)

* [ ] `rules/header_inference.yaml` (weights/thresholds from Stage-01 validator)
* [ ] `rules/table_confidence.yaml` (Stage-07 low-confidence thresholds)
* [ ] `rules/summarizer.yaml` (max lengths, bullet counts)
* [ ] Loader with validation + unit tests; stages read these instead of literals

---

## 6) Observability

* [ ] Per-stage `logs/` bundle:

  * [ ] `request_info.json` (model, token estimates, image counts)
  * [ ] `context_snippet.txt` (first N chars)
  * [ ] `raw_response.txt` (verbatim)
  * [ ] `parsed.json` (validated)
  * [ ] `contract_verdict.json` (pass/fail + reason)
* [ ] Status table printed after each run: counts by pass/fail and error codes
* [ ] `scripts/trace_last_failure.py` to open the latest failing artifact

---

## 7) CI Wiring

* [ ] Job matrix:

  * [ ] `smoke-env`
  * [ ] `pytest -k smoke -q` (no external calls beyond file I/O)
  * [ ] `pytest -k contracts -q`
  * [ ] `pytest -k golden -q` (allow update only with label `golden-approve`)
* [ ] Cache: pip, model downloads (if any), test artifacts retention for 7 days
* [ ] Mark **LLM-hitting** tests as `@slow` and run nightly; PR CI runs offline/text-only versions

---

## 8) Stage-by-Stage Tasks (execution order)

### 8.1 Stage 01 — Annotations

* [ ] Verify smoke (limit=1, images on, no LLM)
* [ ] Normalize FreeText note parsing; write unit tests
* [ ] Ensure `image_output/annot_*.png` saved deterministically
* [ ] Save `.clean.pdf` always; handle “no annotations” path
* [ ] Adopt rule table (weights) from `rules/header_inference.yaml`

### 8.2 Stage 02 — Marker

* [ ] `--no-spawn` path green on fixtures
* [ ] Confirm fonts/first span info; add unit for bbox normalization
* [ ] Fail early if converter missing; helpful error text

### 8.3 Stage 03 — Suspicious Headers

* [ ] Offline pass (`--skip-llm`) green
* [ ] Preflight vision (limit ≤3): confirm images rendered and VLM JSON adheres
* [ ] Wire to `llm_adapter.verify_header` + schema; drop direct `litellm_call`

### 8.4 Stage 04 — Sections

* [ ] Fallback heuristics toggled via flag; defaults trust Stage-03 results
* [ ] Visual composites capped by pages; ensure bounds clamp
* [ ] Unit test for `derive_section_depth` and numbering analysis

### 8.5 Stage 05 — Tables

* [ ] Lattice baseline + fallback strategies; record durations/choices
* [ ] Ensure per-page best table selection determinism
* [ ] Coalesce header repeats tests; image clipping verified

### 8.6 Stage 06 — Figures

* [ ] Smoke with `--skip-descriptions` green
* [ ] (Later) Swap in `llm_adapter.summarize_section` for captions if needed, with cap

### 8.7 Stage 07 — Reflow (critical)

* [ ] Text-only run (`--no-include-images`, compact guard) must produce **valid `reflowed_json`**
* [ ] Multimodal run (`--include-images`) limited to `STAGE07_MAX_IMAGES`
* [ ] All parsing via adapter; invalid JSON → **fail fast** (unless `--allow-fallback`)
* [ ] Table integrity rules: no cell edits; validate against pandas metrics

### 8.8 Stage 08 — Lean (optional now)

* [ ] Run with `--skip-proving` only; produce requirement skeletons
* [ ] CLI integration placeholder documented for later

### 8.9 Stage 09 — Summaries

* [ ] Rolling window summarization; strict JSON mode by default
* [ ] Contract tests for summary schema; golden set for phrasing drift

### 8.10 Stage 10–12 — Flatten/Graph/Annotations (optional DB)

* [ ] Flatten only (`--skip-export`) smoke green; JSON shape documented
* [ ] Graph edges JSON only (`--skip-graph-creation`) green
* [ ] Annotations bridge **debug-bundle** pass

### 8.11 Stage 14 — Report

* [ ] Aggregate canonical filenames; produce `final_report.json/md`
* [ ] Include stage timings and quality score; unit for empty directory handling

---

## 9) Agent Work Loop (SST: Select → Shape → Test)

Per PR:

* [ ] **Select** one micro-target (e.g., “Stage-07 JSON adherence with Gemini”)
* [ ] **Shape**: edit only prompts/rules/adapter config; include prompt version bump
* [ ] **Test**:

  * [ ] Run relevant **smoke target(s)**
  * [ ] Run **contract tests** for the adapter
  * [ ] Run affected **goldens** (show diff if wording changes)
* [ ] Attach artifacts (`logs/…`) for any failing case
* [ ] Record what knobs changed (env/config) and why

---

## 10) Documentation (short, practical)

* [ ] `docs/runbook.md` — “If X fails, do Y” (timeouts, compact guard, drop images)
* [ ] `docs/observability.md` — where to find which artifact
* [ ] `docs/prompts.md` — prompt folders, versioning, linter rules
* [ ] `docs/rules.md` — YAML reference & semantics
* [ ] `CONTRIBUTING_AGENT.md` — summarized checklist above

---

## 11) Definition of Done (per stage)

* [ ] Green **smoke** for that stage on fixtures
* [ ] All **contracts** validate; no lenient parsing
* [ ] Touches **only** allowed areas (or explicit human approval)
* [ ] Artifacts written; report lists pass counts
* [ ] Prompt versions bumped and captured in outputs

---

## 12) Rollout Plan

* [ ] Phase 1 (core offline path): Stages 01–06 + 07 (text-only) + 09 + 14
* [ ] Phase 2 (vision path): 07 multimodal; small doc first
* [ ] Phase 3 (optional DB): 10–12 flatten/graph/bridge in a test DB
* [ ] Phase 4 (nightly): enable slow LLM tests; track drift on goldens

---

## Quickstart Commands (agent can run)

* [ ] `make smoke-env`
* [ ] `make smoke-01 smoke-02 smoke-03-offline smoke-04`
* [ ] `make smoke-05 smoke-06`
* [ ] `make smoke-07-text` (must pass before any vision work)
* [ ] `make smoke-07-vision` (limited images)
* [ ] `make smoke-09 smoke-10-flat smoke-11-nodb smoke-14`

---

This list is long, but the agent works **one box at a time** inside the safe lane (prompts, rules, adapters). You keep control of the deterministic system. When you’re ready, I can generate the initial `contracts.py`, `llm_adapter/adapter.py`, `Makefile`, and the four fixtures so you have a running start.
