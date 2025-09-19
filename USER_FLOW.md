## User Flow — UX ↔ Pipeline (Happy Path, End-to-End)

This is the canonical, testable flow connecting the Classic/Tabbed UI to the extractor pipeline. It uses:
- Single CLI surface: `python -m src.cli extract` (fast|accurate), per docs/03_guides/HAPPYPATH_GUIDE.md
- Deterministic UI selectors (data-testid) verified by smokes
- Backend endpoints in prototypes/tabbed/api/server.py

For acceptance, every step references at least one health marker or smoke.

**Pre‑flight**
- Start dev: `./scripts/dev.sh` (FastAPI :8000, Vite :8080)
- Open `http://127.0.0.1:8080/main` and confirm:
  - `[data-testid="app-ready"]` present, `[data-testid="top-toolbar"]` rendered, `[data-testid="page-label"]` shows N / M
- Health gate: `BASE_URL=http://127.0.0.1:8080/main node scripts/ux_check_broken.mjs` (saves `scripts/artifacts/ux_check_*.{log,png}`)

**1) Open a PDF (UI)**
- Route: `/main` (Classic)
- Default autoload: BHT CV32A65X.pdf (dev sample)
- Markers: `app-ready`, `top-toolbar`, `page-label`
- Optional rails: vertical `[left]` or bottom thumbnails via toolbar toggles

**2) Annotate regions (UI → teaching signal)**
- Draw: press `N` (or HUD “New Box”) and drag on the canvas overlay `[data-testid="overlay"]`
- Label: inspector palette (Sec/Tbl/Fig). Filters echo the same types.
- Notes & mentions: `[data-testid="notes-input"]` supports `@name` autocomplete (local recent reviewers)
- Acceptance (smokes): `ui_grouping_export_json.mjs`, `ui_export_json_fields.mjs`, `ui_mentions_basic.mjs`

Pipeline mapping
- Stage 01: Annotation Processor ingests UI boxes/types
- Stage 05/06: Tables/Figures evidence
- Stage 03/04: Suspicious headers/Section builder structure

**3) Generate extraction artifacts**
- CLI (paved road):
  - Accurate (normalized outputs):
    `python -m src.cli extract input.pdf out/ --mode accurate`
  - Fast (text-only):
    `python -m src.cli extract input.pdf out/ --mode fast`
  - Optional proving:
    `python -m src.cli extract input.pdf out/ --mode accurate --prove`

- UI bridge (dev convenience):
  - Save annotations: `[data-testid="btn-save-annotations"]` → POST `/api/annotations/save`
    - Writes UI-normalized JSON and Stage‑01 canonical JSON
  - Run pipeline: `[data-testid="btn-extract-pipeline"]` → POST `/api/pipeline/run-external`
    - Calls run_all with UI annotations; writes `scripts/artifacts/latest_results.json` pointer
  - Progress banner: `[data-testid="pipeline-progress"]` while running
  - Acceptance (smokes): `ui_progress_pipeline_run.mjs`

Downstream stages for “accurate”
- 07 Reflow, 09 Summarizer, 10 Export (flattened), 11 Graph (optional), 14 Report (final)

**4) Load pipeline annotations into the UI**
- Action: `[data-testid="btn-load-pipeline-annos"]`
- Server: GET `/api/pipeline/latest` → results_dir → read 04/05/06 JSON via `/api/artifacts/file?path=…`
- UI: convert stage bboxes to normalized overlay boxes (uses pdf.js page sizes) and render on current page
- Acceptance (smokes): `ui_load_pipeline_annos_from_latest.mjs` (offline-friendly: verifies overlays or request trail)

**5) Review, filter, claim/assign**
- Paging: `btn-first/prev/next/last`, `page-slider`, `page-number`
- Filters: `filter-type-*`, `filter-confidence`, `filter-owner`
- Review: `btn-claim`, `btn-release` updates `[data-testid="status-badge"]`
- Conflicts: `conflicts-tab`, synthetic `conflict-item` list with adjudication toggle (localStorage)
- Acceptance (smokes): `ui_pagination.mjs`, `ui_filters_basic.mjs`, `ui_conflicts_panel.mjs`, `ui_review_queue.mjs`

**6) Upsert graph/exports (optional, offline‑friendly)**
- Action: `[data-testid="btn-upsert-pipeline"]` → POST `/api/pipeline/upsert`
- Artifacts: Stage‑10 flattened JSON, Stage‑11 graph confirmation; status dot aria-label: `'db-ready'|'db-missing'`
- Report: Stage‑14 (`final_report.md`) linked in toasts when available
- Acceptance (smokes): pipeline reqif/rtm/graph smokes under `scripts/smokes/pipeline/…`

**CLI Cheatsheet (single surface)**
- Accurate: `python -m src.cli extract --mode accurate input.pdf out/`
- Fast: `python -m src.cli extract --mode fast input.pdf out/`
- Prove: `python -m src.cli extract --mode accurate --prove input.pdf out/`

**Selectors the UI must keep stable**
- Mount/health: `app-ready`, `top-toolbar`, `page-label`
- Paging: `btn-first`, `btn-prev`, `btn-next`, `btn-last`, `page-slider`, `page-number`, `pager-prev`, `pager-next`
- Search: `search-input`, `search-prev`, `search-next`, `search-hit`
- Filters: `filter-type-section/table/figure`, `filter-owner`, `filter-confidence`
- Pipeline: `btn-extract-pipeline`, `btn-load-pipeline-annos`, `btn-save-annotations`, `btn-upsert-pipeline`, `pipeline-progress`
- Overlays: `overlay`, `box`, `box-chip`
- Review/collab: `btn-claim`, `btn-release`, `status-badge`, `notes-input`, `mention-suggest`, `conflicts-tab`, `conflict-item`, `btn-adjudicate`

**Why this alignment matters**
- One paved road from UI → pipeline → artifacts, with objective gates and artifacts.
- Reduces ambiguity by binding every UI action to a pipeline stage and server endpoint.
- Matches Happy Path so operators and contributors share one canonical, smoke‑verified flow.
