# Task Plan: Pipeline + CLI Polish and Guardrails (2025‑09‑18)

Purpose
- Harden the paved‑road experience (CLI → pipeline → UX) with small, low‑risk changes.
- Add pre‑flight smokes (completion boxes) before code changes to avoid regressions.
- Keep surface area minimal; avoid brittleness.

## 0) Pre‑Flight Checklist
- [ ] All work in a short branch (or PR bundle if required)
- [ ] Run current non‑UI smokes: fast PDF, structured‑all, Stage 05 quality, meta parity
- [ ] Confirm dev servers boot (scripts/dev.sh), no Vite overlay/console errors (ux‑health)

## 1) Smokes To Add (FIRST)

Aligned strictly to docs/03_guides/HAPPYPATH_GUIDE.md

1. CLI Fast PDF
- File: `scripts/smokes/pipeline/smoke_cli_fast_pdf.py`
- What: `python -m src.cli extract <pdf> <out_dir> --mode fast` completes and emits `<out_dir>/<stem>_fast.json`.
- Acceptance:
  - Artifacts: `scripts/artifacts/cli_fast_pdf.json` with {ok, out_dir}
  - Fails if command or artifact missing.
- [ ] Implement smoke

2. CLI Structured (single format)
- File: `scripts/smokes/pipeline/smoke_cli_structured.py`
- What: `python -m src.cli extract <html|docx|...> <out_dir>` completes and emits Stage 07 + 10 artifacts in canonical layout.
- Acceptance:
  - Artifacts: `scripts/artifacts/cli_structured.json` with {ok, stage07, stage10}
  - Fails if 07/10 missing.
- [ ] Implement smoke

3. CLI Structured All Providers
- File: `scripts/smokes/pipeline/smoke_cli_structured_all.py`
- What: Iterate supported providers (HTML, DOCX, PPTX, XLSX, EPUB, RST, XML, MD) and verify Stage 07 + 10 outputs for each sample.
- Acceptance:
  - Artifacts: `scripts/artifacts/cli_structured_all.json` with per‑provider results
  - Fails only on missing Stage 10 for any provider.
- [ ] Implement smoke

4. Stage 05 Strategy Quality
- File: `scripts/smokes/pipeline/smoke_stage05_strategy_quality.py`
- What: Accurate PDF path yields table extraction quality above minimum bars (present per guide).
- Acceptance:
  - Artifacts: `scripts/artifacts/stage05_strategy_quality.json` with {ok, metrics}
  - Fails if quality metrics below threshold.
- [ ] Implement smoke

5. Meta Parity Across Formats
- File: `scripts/smokes/pipeline/smoke_meta_parity_all_formats.py`
- What: Parity of core metadata presence between accurate PDF and structured providers.
- Acceptance:
  - Artifacts: `scripts/artifacts/meta_parity_all_formats.json` summary
  - Fails if required presence missing.
- [ ] Implement smoke

6. Single CLI Surface (no legacy verbs)
- File: `scripts/smokes/pipeline/smoke_cli_single_surface.mjs`
- What: Only `python -m src.cli extract` is allowed. Running any legacy commands (e.g., `extract-pdf`, `convert_single.py`) must fail with a helpful message.
- Acceptance:
  - Artifacts: `scripts/artifacts/cli_single_surface.json` with {ok, rejected: [cmds]}
  - Fails if legacy entry points succeed or produce non-deprecation output.
- [ ] Implement smoke

7. CLI PDF Modes Parity (fast vs accurate)
- File: `scripts/smokes/pipeline/smoke_cli_pdf_modes.mjs`
- What: For a small sample PDF, ensure both `--mode fast` and `--mode accurate` complete and emit schema-valid Stage 03/05/07 artifacts.
- Acceptance:
  - Artifacts: `scripts/artifacts/cli_pdf_modes.json` with {ok_fast, ok_accurate, schema_ok}
  - Fails on schema invalid or missing Stage 03/05/07.
- [ ] Implement smoke

Deferred (outside Happy Path scope)
- RTM links smoke
- ReqIF export round‑trip

## 2) Code Changes (AFTER Smokes)

A. Enforce Single CLI Surface
- Deprecate any alternate entry points in help output; ensure `python -m src.cli extract` routes all formats.
- Reject legacy verbs with a helpful message.
- [ ] Implement

Deferred (outside Happy Path scope)
- JSON schema validation + single retry
- OCR language/preprocessing toggles
- Quality‑aware table fallback
- Meta parity deltas enhancement

F. Provider Polish (Non‑breaking, HP‑compliant)
- Deprecate: `src/extractor/core/scripts/convert_single.py` with banner and pointer to `python -m src.cli extract`.
- Remove unused import: `src/extractor/core/providers/pptx.py` (MSO_THEME_COLOR).
- Guard private API: `src/extractor/core/providers/spreadsheet.py` protect `ws._images` access (try/except).
- Provider docstrings: minor cleanups (HTML/PPTX/XML/RST/Spreadsheet).
- [ ] Add deprecation banner (convert_single)
- [ ] Remove PPTX unused import
- [ ] Spreadsheet images guard
- [ ] Provider docstrings updated



## 3) Documentation & Examples
- README: add CLI examples for fast/accurate and troubleshooting for accurate mode
- CONTRIBUTING: keep ruff/smokes commands (already added), reference new smokes
- [ ] Update README
- [ ] Update CONTRIBUTING (smokes list)

3b) Happy Path Alignment (Single CLI Surface)
- Sweep all docs (README, `docs/03_guides/HAPPYPATH_GUIDE.md`, `docs/SMOKES_GUIDE.md`, any lingering `extract-pdf` refs) to point exclusively to `python -m src.cli extract`.
- Add a short “Why one CLI” section and examples for PDF fast/accurate and structured formats (HTML, DOCX, PPTX, XLSX, XML, RST, MD).
- [ ] Sweep and replace legacy verbs
- [ ] Add troubleshooting notes (accurate mode) and environment hints

## 4) UX (Tabbed) — Deferred per Happy Path
- Do not modify prototypes or add UX health checks under this task.

## 5) Acceptance (Definition of Done)
- CLI fast & accurate pass on sample PDF
- Happy Path smokes GREEN (items 1–5)
- Single CLI surface enforced (legacy verbs rejected with message)
- README/CONTRIBUTING updated with examples and HP smokes

5b) Compliance Gates
- [ ] Commands and examples in `docs/03_guides/HAPPYPATH_GUIDE.md` match the single CLI.
- [ ] Smokes listed in `docs/SMOKES_GUIDE.md` include all new smokes with acceptance and artifact paths.

## 6) Traceability (Artifacts to Expect)
- `scripts/artifacts/cli_fast_pdf.json`
- `scripts/artifacts/cli_structured.json`
- `scripts/artifacts/cli_structured_all.json`
- `scripts/artifacts/stage05_strategy_quality.json`
- `scripts/artifacts/meta_parity_all_formats.json`

6b) New Artifacts (added in this patch plan)
- `scripts/artifacts/cli_single_surface.json`
- `scripts/artifacts/cli_pdf_modes.json`

## 7) Ownership & Timebox
- CLI enforcement + provider polish: Eng A: 0.5–1d
- HP smokes (1–5) + docs sweep: Eng A: 1–1.5d

---

## Completion Boxes (Roll‑up)
- [ ] Implement HP smokes (items 1–5) and run them
- [ ] Single CLI surface enforced; legacy verbs deprecated
- [ ] Provider polish (pptx import, spreadsheet guard, docstrings)
- [ ] README/CONTRIBUTING updated with examples and HP smokes

Additional Completion
- [ ] CLI PDF modes parity smoke passing
- [ ] Docs Happy Path/Smokes guides aligned to CLI

---

## Quick‑Run Commands (copy/paste)

Run Happy Path smokes
```bash
PYTHONPATH=src \
  uv run scripts/smokes/pipeline/smoke_cli_fast_pdf.py && \
PYTHONPATH=src \
  uv run scripts/smokes/pipeline/smoke_cli_structured.py && \
PYTHONPATH=src \
  uv run scripts/smokes/pipeline/smoke_cli_structured_all.py && \
PYTHONPATH=src \
  uv run scripts/smokes/pipeline/smoke_stage05_strategy_quality.py && \
PYTHONPATH=src \
  uv run scripts/smokes/pipeline/smoke_meta_parity_all_formats.py
```

CLI surface and modes
```bash
node scripts/smokes/pipeline/smoke_cli_single_surface.mjs && \
node scripts/smokes/pipeline/smoke_cli_pdf_modes.mjs
```
