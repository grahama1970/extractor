Below is the **amended master checklist** that bakes iteration into the system (not just a one-time task list). It assumes we’re pivoting away from vibe-coding to a **contracts + smokes + GitHub-issue loop** where every defect becomes a permanent test and the agent operates inside small, checkable loops.

Use this exactly as your shared source of truth. The agent must follow it line-by-line; every step has a required artifact.

---

# Pivot Plan v2 — Delivery & Iteration Checklists

**Context:**
We previously shipped a long checklist, then drowned in post-“done” bugs and prompt drift. This plan makes *iteration* the core of the system: every issue becomes a failing test first; fixes are only allowed if they turn that test green *and* pass gates.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done
Owner tags: `(Agent)`, `(Human)`, `(CI)`

---

## 0) Roles, Boundaries, and Repo Guardrails (one-time)

* [ ] (Human) Add `CONTRIBUTING_AGENT.md` with:

  * [ ] Allowed changes: `prompts/**`, `rules/**`, `llm_adapter/**`, `tests/**`, CI configs.
  * [ ] Forbidden without human approval: stage core logic, DB schema, infra.
  * [ ] “Fix = test first” policy and **defect-to-test** SOP (see Section 6).
* [ ] (Human) Add CODEOWNERS: deterministic pipeline files require human review.
* [ ] (CI) Protect main: require **Gates** (Section 5) to pass; block merges with quarantines.
* [ ] (Human) Add `docs/iteration.md` (short, operational): defect capture → test → fix → ratchet.

**Artifacts:** `CONTRIBUTING_AGENT.md`, `docs/iteration.md`, CODEOWNERS.

---

## 1) Repository Structure & Minimal Fixtures

* [ ] (Human) Create dirs:

  * [ ] `prompts/{03_header,07_reflow,09_summary}/...`
  * [ ] `rules/{header_inference.yaml, table_confidence.yaml, summarizer.yaml}`
  * [ ] `llm_adapter/adapter.py` (single entrypoints; strict schema validation)
  * [ ] `tests/smoke/**`, `tests/contracts/**`, `tests/golden/**`, `tests/fixtures/**`
* [ ] (Human) Add **fixtures** PDFs (tiny, deterministic):

  * [ ] `one_annot.pdf`, `table_simple.pdf`, `headers_mixed.pdf`, `figures_basic.pdf`

**Artifacts:** tree exists; fixtures committed.

---

## 2) Adapter & Contract Layer (firebreak around LLMs)

* [ ] (Agent) Implement `llm_adapter/adapter.py`:

  * [ ] Entrypoints: `verify_header(...)`, `reflow_section(...)`, `summarize_section(...)`
  * [ ] Force `response_format={"type":"json_object"}` where supported; strict timeouts; retries.
  * [ ] Validate against **Pydantic** contracts (below); reject extra/missing keys.
  * [ ] Dump per-call bundle: `logs/{stage}/{id}/{req.json, raw.txt, parsed.json, verdict.json}`
  * [ ] Redact secrets; clip contexts to byte caps (env).
* [ ] (Agent) Define **contracts** in `contracts.py`:

  * [ ] `HeaderVerdict`, `ReflowedSection` (with `reflowed_json`), `SectionSummary` schemas.
  * [ ] Unit tests: invalid/missing/extra keys hard-fail.

**Artifacts:** adapter+contracts files; passing unit tests.

---

## 3) Prompts & Rules as Code (governed, versioned)

* [ ] (Agent) Move prompts into `prompts/**`; include `prompt_version: "name@x.y.z"` echoed in outputs.
* [ ] (Agent) Add `tools/prompt_lint.py`:

  * [ ] Enforce “Return ONLY JSON …” and token budget comments.
  * [ ] Ban hedges (“maybe”, “approximately”, etc.) and code fences.
* [ ] (Agent) Parameterize heuristics into `rules/**` (YAML):

  * [ ] `header_inference.yaml` (weights/thresholds)
  * [ ] `table_confidence.yaml` (low-confidence cutoff for image attachment)
  * [ ] `summarizer.yaml` (lengths, bullets)

**Artifacts:** prompt files with versions, rule YAMLs, prompt-lint passing.

---

## 4) Test Pyramid (fast, layered)

* [ ] (Agent) **Smokes** (CLI slices; ≤10s each). Add make targets & pytest:

  * [ ] Stage-01 annotations (images saved; clean PDF)
  * [ ] Stage-02 marker `--no-spawn`
  * [ ] Stage-03 offline & limit=3 vision preflight
  * [ ] Stage-04 sections (+ visuals)
  * [ ] Stage-05 tables (Camelot lattice baseline)
  * [ ] Stage-06 figures (`--skip-descriptions`)
  * [ ] Stage-07 text-only (strict JSON) and multimodal (limited images)
  * [ ] Stage-09 summaries (strict JSON)
* [ ] (Agent) **Contract tests**: schemas in `tests/contracts/**` (pydantic).
* [ ] (Agent) **Goldens**: 5–20 micro PDFs + expected JSON outputs.

  * [ ] Ratchet policy: updates require label `golden-approve` and reviewer note.

**Artifacts:** test files; `pytest -k 'smoke or contracts or golden'` passes locally.

---

## 5) CI/CD Quality Gates (non-negotiable)

* [ ] (CI) Gate 1 — **Schema**: `pytest -k contracts -q` must be 100%.
* [ ] (CI) Gate 2 — **Goldens**: `pytest -k golden -q`; diffs only with `golden-approve`.
* [ ] (CI) Gate 3 — **Smokes (subset)**: 01→04 path, 05, 07-text, 09; ≤5m total.
* [ ] (CI) Gate 4 — **Quarantines**: **zero** `xfail` on main.
* [ ] (CI) Gate 5 — **Drift**: prompt/model version must be present in outputs (fail missing).
* [ ] (Nightly CI) Full smokes, 07-vision, canary set (Section 9); regressions open issues automatically.

**Artifacts:** GitHub Actions workflows configured; badges/required checks on branch protection.

---

## 6) GitHub Issue → Test → Fix Protocol (the loop)

* [ ] (Human) Add **Issue Template** `.github/ISSUE_TEMPLATE/bug.md`:

  ```
  ### Stage(s): e.g., 03_suspicious_headers
  ### Expected vs Actual:
  ### Repro input: (PDF / bundle path)
  ### Attachments: screenshots/raw outputs if any
  ```

* [ ] (Agent) For **every new issue**:

  * [ ] Create a **failing test first**:

    * [ ] Contract test for shape/format bugs
    * [ ] Golden test for semantic misclassification
    * [ ] Micro-smoke for systemic stage behavior
  * [ ] Run suite; comment with path & failing output snippet.
  * [ ] Propose **smallest fix** (prompt/rule/adapter), not pipeline code.
  * [ ] Re-run: new test + required smokes + contracts + goldens.
  * [ ] Link PR; close issue only when everything is green.

* [ ] (CI) Require PRs that close issues to include a new/updated test touching that path.

**Artifacts:** issue template; PR checklist; example issue closed with linked test + fix.

---

## 7) Stabilization Cadence & Quarantine Management

* [ ] (Human) Adopt **A/B cadence**:

  * [ ] Week A (Stabilize): only fix quarantines/flakes; no new features.
  * [ ] Week B (Expand): new features allowed; defects follow the loop.
* [ ] (Agent) Flake detector:

  * [ ] If intermittent: mark `xfail` with `quarantine: reason`, auto-open ticket.
  * [ ] Replace with deterministic mode (e.g., 07 text-only compact guard) in CI.

**Artifacts:** backlog label “quarantine”; dashboard counts; zero quarantines on main.

---

## 8) Observability (see what the model saw)

* [ ] (Agent) Per-call dumps (already in adapter): `req.json`, `context_snippet.txt`, `raw.txt`, `parsed.json`, `verdict.json`.
* [ ] (Agent) `scripts/trace_last_failure.py` that:

  * [ ] Finds the last failing test
  * [ ] Opens the matching log bundle path
* [ ] (CI) Artifact retention 7 days for failing runs.

**Artifacts:** logs folder populated; trace script works in CI artifacts.

---

## 9) Canaries & Shadow Runs (prevent silent drift)

* [ ] (Human) Define 10-PDF **canary set** (manuals, datasheets, scans, edge fonts).
* [ ] (Nightly CI) Run:

  * [ ] 07 text-only and 07 vision on canaries
  * [ ] Compare JSON validity %, table shapes, header accept/reject diffs vs last green
  * [ ] Auto-open regression issues with diff summaries
* [ ] (Agent) Shadow runs when switching provider/model: run both, compare keys and metrics; don’t flip default until drift is understood.

**Artifacts:** nightly report, auto-created issues on regression.

---

## 10) Metrics & SLOs (only what predicts pain)

* [ ] (Agent/CI) Track:

  * [ ] Stage-07 JSON Validity % (SLO ≥ 99.5% weekly)
  * [ ] Header verification precision/recall on goldens
  * [ ] **Table cell mutation rate** during reflow (must be 0)
  * [ ] Median wall-time per stage (catch regressions)
  * [ ] Quarantine count (must be 0 on main)
* [ ] (Human) Assign owners per metric; alerts route to them.

**Artifacts:** simple metrics JSON + Slack/issue alerts; SLO doc.

---

## 11) UX / Screenshot-Driven Issues (optional but supported)

* [ ] (Human) For UI regressions, attach **before/after** screenshots.
* [ ] (Agent) Create **visual smoke**:

  * [ ] Add fixture image(s) under `tests/fixtures/ux/`
  * [ ] Use simple SSIM/threshold or DOM text assert (keep deterministic)
  * [ ] Test fails without fix; succeeds after
* [ ] (Agent) Keep visual smokes *tiny* and specific (one widget per test).

**Artifacts:** visual test file; passing locally & CI.

---

## 12) Definition of Done (per Issue, per Stage)

* [ ] (Agent) Issue closed only when:

  * [ ] New failing test added → now green
  * [ ] Gates (Section 5) are green
  * [ ] Prompt version bumped & echoed in outputs
  * [ ] Logs present; fix scope documented in PR body
* [ ] (Human) Stage DoD:

  * [ ] Smokes green on fixtures
  * [ ] Contracts 100%
  * [ ] No quarantines
  * [ ] Canaries green for a week

---

## 13) Practical Agent Rules (must follow)

* [ ] Do **not** edit pipeline core without human approval.
* [ ] Fixes must be in **prompts, rules, or adapter settings** first.
* [ ] If a bug can’t be reproduced, create a **minimal smoke** that fails; if still not reproducible, **stop and report** with artifacts.
* [ ] Cap changes per PR: ≤30 prompt lines, ≤3 rule tweaks, ≤1 adapter parameter set change.
* [ ] Always include: failing test path → fix diff → passing run evidence.

---

## 14) Quick Start Targets (for agent & humans)

* [ ] `make smoke-env`
* [ ] `make smoke-01 smoke-02 smoke-03-offline smoke-04`
* [ ] `make smoke-05 smoke-06`
* [ ] `make smoke-07-text` (must pass before vision)
* [ ] `make smoke-07-vision` (limited images)
* [ ] `make smoke-09`
* [ ] `make smoke-10-flat smoke-11-nodb`
* [ ] `make smoke-14`

---

### Why this avoids “AI slop”

* **Bugs become tests**, so the suite only grows more protective.
* **Quality gates** make it impossible to “pass CI” with sloppy changes.
* **Adapters & contracts** wall off LLM chaos from your deterministic code.
* **Prompt versioning + canaries** expose drift immediately.
* **Small PR scope** limits blast radius.

If you want, I can generate the initial files for: `contracts.py`, `llm_adapter/adapter.py` skeleton, the smoke Makefile, the issue template, and a couple of exemplar tests—so you can commit this structure and start the loop right away.

