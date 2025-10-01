# Smoke Tests Guide

This guide explains how we design, implement, and maintain smoke tests across the repository. It synthesizes the current workflow (see `prototypes/tabbed/docs/workflow.md`) and the smoke suites under `scripts/smokes/`, `tests/smoke/`, and `scripts/artifacts/`.

---

## 1. Purpose

- **Verify viability**: Smokes prove that core paths execute without fatal regressions. They are intentionally lightweight and deterministic.
- **Document acceptance**: Each issue includes a failing smoke that captures the desired user outcome before we touch production code.
- **Produce artifacts**: Every run saves logs/screenshots to `scripts/artifacts/` so reviewers can confirm real UI/API state.

Smokes do **not** replace full unit or integration tests; they guard the happy path while longer suites catch edge cases.

---

## 2. Taxonomy

| Category | Location | Typical Trigger |
| --- | --- | --- |
| **UI (Tabbed prototype)** | `scripts/smokes/issue_*.mjs`, `scripts/ux_check_*.mjs` | Visual regressions, toolbar states, pointer draw |
| **API / Pipeline** | `scripts/smokes/pipeline/*.py`, `tests/pipeline/test_run_all_smoke.py` | Stage-specific behaviors, CLI execution |
| **CLI / Tooling** | `scripts/codex_smoke.py`, `scripts/smoke_litellm_parallel.py`, `tests/smoke/test_*` | Contract checks for Typer CLIs and adapters |

Each new feature chooses the closest category and extends it with a dedicated smoke file.

---

## 3. Authoring Workflow

1. **Define acceptance**
   - Capture the scenario in an issue (`prototypes/tabbed/issues/NNN_slug.md`).
   - Acceptance must reference concrete selectors, API responses, or observable state.

2. **Scaffold the smoke**
   - UI: use VS Code task `Issue: Scaffold (tabbed)` to create `scripts/smokes/issue_NNN.mjs`.
   - API/CLI: create a Python script under `scripts/smokes/` with a uv metadata header, or add a pytest case under `tests/smoke/`.

3. **Make it fail for the right reason**
   - Run the smoke before implementing the fix and confirm it fails with an actionable message.
   - Example UI command:
     ```bash
     BASE_URL=http://127.0.0.1:8080 node scripts/smokes/issue_007.mjs
     ```

4. **Implement the minimal fix**
   - Update code, prompts, or configs so the smoke logic passes.

5. **Capture artifacts**
   - UI: `npm run ux:check` or `node scripts/ux_check_cdp_auto.mjs` (saves to `scripts/artifacts/`).
   - API: redirect output to `scripts/artifacts/issue_NNN_*.log` for review.

6. **Verify suites**
   - Core checks: `ruff check . && black --check . && mypy src && pytest -q`.
   - Consolidated: `scripts/ci_local.sh` or `make ci` (runs smokes + health gates).

7. **Document results**
   - Paste artifact paths into the issue under “Artifacts”.
   - Note the smoke file under “Smokes to add”.

---

## 4. Implementation Patterns

### 4.1 JavaScript (Puppeteer) smokes

- Use the scaffolding template in `scripts/smokes/issue_NNN.mjs`:
  ```js
  import { expect } from "expect";
  import { launchPage } from "../cdp/utils.mjs";

  const BASE = process.env.BASE_URL ?? "http://127.0.0.1:8080";

  export default async function run() {
    const { page, close } = await launchPage({ baseUrl: BASE });
    try {
      await page.goto(`${BASE}/classic`);
      await page.waitForSelector('[data-testid="page-label"]');
      // Assertions...
    } finally {
      await close();
    }
  }
  ```
- Prefer `data-testid` hooks; avoid brittle CSS positional selectors.
- Wait for `[data-testid="page-label"]` to guarantee the app mounted.
- Collect extra diagnostics via `page.screenshot` and custom logs when needed.

### 4.2 Python smokes

- Start files with a uv header so agents can run them outside the repo venv.
- Prefer the Typer-based reference pattern used by `scripts/smokes/pipeline/smoke_stage05_camelot_linewidth.py`:
  ```python
  #!/usr/bin/env -S uv run --script
  # /// script
  # requires-python = ">=3.10"
  # dependencies = [
  #   "typer>=0.12",
  #   "python-dotenv",
  # ]
  # ///
  import sys
  import typer

  app = typer.Typer(add_completion=False)


  def run_smoke(...):
      """Perform assertions, raise SystemExit on failure."""
      ...


  @app.command()
  def main(...):
      run_smoke(...)


  if __name__ == "__main__":
      if len(sys.argv) > 1:
          app()
      else:
          run_smoke(defaults...)
  ```
- The `uv run --script` shebang ensures dependencies resolve automatically in clean environments.
- Direct invocation (`python smoke.py`) runs the CLI when arguments are supplied and falls back to default parameters when none are provided.
- Always exit non-zero on failure and print actionable messages.
- Store artifacts/logs beneath `scripts/artifacts/` with timestamps.

### 4.3 Pytest smokes

- Mirror source structure under `tests/smoke/` (see `tests/smoke/test_stage05_tables_smoke.py`).
- Use fixtures to synthesize inputs; keep runtime < 5 seconds.
- Mark with `@pytest.mark.smoke` so suites can target them.

### 4.4 Pipeline (UnifiedDocument) smokes

- Stage 07 now ships both the legacy `reflowed_sections` bundle and a
  canonical `unified_document` payload. Smokes that exercise the pipeline must
  assert that the normalized document exists and validates against
  `extractor.core.schema.unified_document`.
- Stage 10 exporters consume only the unified schema. Smokes should diff the
  flattened output for at least one non-PDF format (HTML/DOCX) and its PDF
  counterpart to ensure Arango payloads remain isomorphic.
- When capturing artifacts, include the generated `unified_document.json` (or
  the Stage 10 flattened JSON) alongside the existing logs so reviewers can
  spot schema regressions quickly.
- `scripts/smokes/pipeline/smoke_structured_pdf_parity.py` compares a PDF Stage 07
  bundle with a structured-format rendition (html, docx, pptx, spreadsheet,
  epub, rst, xml). It saves summaries under `scripts/artifacts/` and should be
  run (and recorded) whenever parity is adjusted.

#### Section-Context Acceptance (structured formats)

For non-PDF formats that already carry structure (HTML, DOCX, PPTX, Spreadsheet, EPUB, RST, XML), prefer presence-based checks with explicit section context over brittle object-count parity:

- Stage 07: `reflowed_sections` exists and is non-empty.
- Stage 10: at least one flattened object has a non-root `section_id`.
- Title mapping: at least one `section_title` in Stage 10 matches a title from Stage 07 (not necessarily the first).

These checks are used by the parity smokes under `scripts/smokes/pipeline/smoke_parity_*.py` and keep acceptance aligned with `docs/03_guides/HAPPYPATH_GUIDE.md`.

---

## 5. Tooling & Commands

- **Local CI**: `scripts/ci_local.sh` runs linting, pytest, and the UX smokes.
- **UX Health Gate**: `npm run ux:check` (Puppeteer) or `node scripts/ux_check_cdp_auto.mjs` for auto discovery.
- **Pipeline stage smokes**: `make smokes-stage07-strict`, `make smokes-python` (see `.github/workflows/python-pipeline-smokes.yml`).
- **Quick pipeline check**: `python src/extractor/pipeline/tools/quick_smoke.py` (ensures CLI wiring).

### New Lean4‑related smokes

- Deterministic env wiring (no Lean4 dependency):
  ```bash
  uv run scripts/smokes/pipeline/smoke_stage08_deterministic_env.py
  # Artifact: scripts/artifacts/lean4_deterministic_env.json
  ```
- Lean4 CLI help (skips if CLI not found):
  ```bash
  uv run scripts/smokes/pipeline/smoke_lean4_cli_deterministic_help.py
  # Artifact: scripts/artifacts/lean4_cli_help_check.json

#### Requirement extraction + proving (offline, deterministic)

- Sentences with modal verbs → Lean4
  ```bash
  uv run scripts/smokes/pipeline/requirements/smoke_sentence_shall.py
  # Artifact: scripts/artifacts/req_sentence_shall_summary.json
  ```
- Bullet list inheritance → Lean4
  ```bash
  uv run scripts/smokes/pipeline/requirements/smoke_bullets_inherit.py
  # Artifact: scripts/artifacts/req_bullets_inherit_summary.json
  ```
- Table constraints → Lean4
  ```bash
  uv run scripts/smokes/pipeline/requirements/smoke_table_constraints.py
  # Artifact: scripts/artifacts/req_table_constraints_summary.json
  ```
- Formal artifact (prove and save .lean)
  ```bash
  uv run scripts/smokes/pipeline/requirements/smoke_lean4_formal_artifact.py
  # Artifacts: scripts/artifacts/lean4_formal_artifact_summary.json, scripts/artifacts/proved_00.lean
  ```

- Merged table → Lean4 requirements (offline)
  ```bash
  uv run scripts/smokes/pipeline/requirements/smoke_table_merge_to_lean4.py
  # Artifacts: scripts/artifacts/merged_table_constraints.json, scripts/artifacts/merged_table_lean4_summary.json
  ```

  ```

### New Graph smokes (Stage 11)

- Proves‑only offline (no embeddings):
  ```bash
  uv run scripts/smokes/pipeline/smoke_stage11_proves_only_offline.py
  # Artifact: scripts/artifacts/stage11_proves_only_offline.json
  ```
- Schema & invariants summary (debug-bundle):
  ```bash
  uv run scripts/smokes/pipeline/smoke_stage11_schema_invariants.py
  # Artifact: scripts/artifacts/stage11_schema_summary.json
  ```

### New Exporter smokes

- JSON‑LD export v0:
  ```bash
  uv run scripts/smokes/pipeline/smoke_jsonld_export.py
  # Artifact: scripts/artifacts/jsonld_export_report.json
  ```
- ReqIF export v0 (with XML validation):
  ```bash
  uv run scripts/smokes/pipeline/smoke_reqif_export.py
  # Artifact: scripts/artifacts/reqif_export_report.json
  ```

### Online Smokes (Opt‑In, Cached)

These make 1 LLM call each and SKIP when no provider keys are set. Enable cache via `litellm_cache` (Redis recommended) to avoid duplicate spend.

Env snippet:
```bash
export LITELLM_MODEL=${LITELLM_MODEL:-openai/gpt-4o-mini}
# set exactly one provider key
# export OPENAI_API_KEY=...
# export ANTHROPIC_API_KEY=...
# export GOOGLE_API_KEY=...
# export AZURE_OPENAI_KEY=...
# optional cache across smokes
# export REDIS_URL=redis://127.0.0.1:6379/0
```

Run:
- `uv run scripts/smokes/pipeline/online/smoke_litellm_sanity.py`
- `uv run scripts/smokes/pipeline/online/smoke_stage07_reflow_llm_json_strict.py`
- `uv run scripts/smokes/pipeline/online/smoke_stage09_summarizer_one.py`
- `uv run scripts/smokes/pipeline/online/smoke_stage11_rationale_one.py`

Use `scripts/artifacts/` as the canonical output directory for logs and screenshots; CI workflows archive this folder.

---

## 6. Maintenance Guidelines

- Update smokes whenever acceptance changes. The smoke should be the first failing signal.
- Avoid flakiness: mock network calls where possible, guard against animation delays, and keep assertions minimal.
- Record flaky cases in `.serena/memories/smokes_status.md` and add links to issues for follow-up.
- When removing a feature, delete its smoke and artifacts to keep the suite lean.

---

## 7. References

- `prototypes/tabbed/docs/workflow.md` – detailed front-end workflow and examples.
- `docs/iteration.md` – iteration loop emphasizing “failing test first”.
- `.github/workflows/smokes.yml` – CI wiring for smoke suites.
- `scripts/smokes/` – canonical location for runnable smokes.
- `tests/smoke/` – pytest-based smokes for pipeline stages.

For questions or improvements, open an issue and tag the maintainers listed in `docs/PreviousContext.md`.
## Blocking Smokes (UI)

- Typecheck (Tabbed UI)
  - `cd prototypes/tabbed/html && npm run typecheck`
- UI health gate (route = `/main`)
  - `BASE_URL=http://127.0.0.1:8080/main npm run ux:check`
  - Pass: no dev overlay; `appReady/rootMounted/uiReady=true`; `pointerDrawOk=true`; `toolbarClear=true`; artifacts saved to `scripts/artifacts/`.
- DOM essentials
  - Inspector pane: `BASE_URL=http://127.0.0.1:8080 node scripts/smokes/ui_inspector_pane_present.mjs`
  - Requirements pane: `BASE_URL=http://127.0.0.1:8080 node scripts/smokes/ui_requirements_pane_dom.mjs`
- Console errors (CDP preferred)
  - `BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser npm run ux:check:cdp`
  - Fallback: `BASE_URL=http://127.0.0.1:8080/main node scripts/smokes/console_errors.mjs`

## Blocking Smokes (Pipeline / Requirements)

- Stage outputs stable: `python scripts/smokes/pipeline/smoke_stage10_flatten.py`
- Graph creation: `python scripts/smokes/pipeline/smoke_stage11_graph.py`
- Final report: `python scripts/smokes/pipeline/smoke_stage14_report.py`
- Requirements summary: `python scripts/smokes/pipeline/acceptance/smoke_requirements_summary.py`

## Advisory (warn‑only) Smokes

- Toolbar tooltips: `node scripts/smokes/ui_toolbar_tooltips.mjs`
- Zoom buttons: `node scripts/smokes/ui_zoom_buttons_present.mjs`
