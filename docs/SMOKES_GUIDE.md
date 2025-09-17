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
