## User Flow (Aligned with Pipeline, CLI, and UX)

This amends the original high‑level flow with concrete references to:
- Pipeline steps under `src/extractor/pipeline/steps`
- The unified CLI (`python -m src.cli extract`)
- Stable UX selectors used by our smokes (data‑testids)

For the Happy Path philosophy and acceptance signals, see also: `docs/03_guides/HAPPYPATH_GUIDE.md`.

### Pre‑flight (dev loop)
- Start backend + Vite: `./scripts/dev.sh` (backs FastAPI on :8000, Vite on :8080).
- Open `http://127.0.0.1:8080/main` and confirm:
  - `data-testid="app-ready"` present
  - `data-testid="top-toolbar"` rendered
  - `data-testid="page-label"` shows pagination

### 1) Load a PDF in the Classic UI
- Route: `/main` (Classic layout)
- UX markers: `app-ready`, `top-toolbar`, `page-label`
- Optional thumbnails: left/bottom rails via toolbar toggles

### 2) Annotate key regions (teaching signal)
- Arm pointer or use toolbar button:
  - Keyboard: press `N` to arm drawing
  - Toolbar: `data-testid="btn-add-annotation-top"`
- Label types via the inspector; selectors used by smokes include:
  - `filter-type-section`, `filter-type-table`, `filter-type-figure`
  - Notes: `notes-input`

Relevant pipeline context (what these labels map to):
- `01_annotation_processor.py` — normalizes annotation boxes/types
- `05_table_extractor.py`, `06_figure_extractor.py` — table/figure evidence
- `03_suspicious_headers.py`, `04_section_builder.py` — section structure

### 3) Generate extraction artifacts
Preferred Happy Path (single surface):
- CLI (accurate PDF):
  - `python -m src.cli extract --mode accurate <input.pdf> <outdir>`
- CLI (fast PDF text only):
  - `python -m src.cli extract --mode fast <input.pdf> <outdir>`
- Optional formalization:
  - `python -m src.cli extract --mode accurate --prove <input.pdf> <outdir>` (Stage 08 Lean4)

After the CLI run completes, load artifacts into the UI:
- Load pipeline annos: `data-testid="btn-load-pipeline-annos"`
- Save/merge edits back: `data-testid="btn-save-annotations"`

Downstream stages touched by “accurate” runs:
- `07_reflow_section.py` — text reflow; `09_section_summarizer.py`
- `10_arangodb_exporter.py` — per‑doc objects exported
- `12_insert_annotations.py` — insert/bridge annotations to DB
- `14_report_generator.py` — summary report

Step‑specific CLIs (Typer apps available):
- `11_arango_create_graph.py` — similarity/graph edges in ArangoDB
- `12_insert_annotations.py` — insert/bridge annotations

### 4) Review and iterate annotations
- Paging: `btn-first`, `btn-prev`, `pager-slider`, `btn-next`, `btn-last`
- Review state: `btn-claim`, `btn-release` (status badge updates)
- Notes & mentions: `notes-input` (persisted per‑doc)
- Conflicts panel: `conflicts-tab`, `conflict-item-*` (adjudication controls TBD)

### 5) Export artifacts from the UI
- JSON export (current page): `btn-export-json`
- COCO (selection): `btn-export-coco-selection`

### 6) Build cross‑document relationships (optional)
- After exporting to Arango (Stage 10), create edges:
  - Run graph builder (Typer app in `11_arango_create_graph.py`)
  - Inspect via project dashboards or API as available

### Quick CLI Cheatsheet
- Extract (single surface):
  - `python -m src.cli extract --mode accurate input.pdf out/`
  - `python -m src.cli extract --mode fast input.pdf out/`
- Step CLIs (advanced):
  - `python -m src.extractor.pipeline.steps.12_insert_annotations --help`
  - `python -m src.extractor.pipeline.steps.11_arango_create_graph --help`

### Smoke Alignment (what the UI must expose)
- Health markers: `app-ready`, absence of dev overlays
- Toolbar paging: `btn-prev`, `btn-next`, `page-label`
- Filters: `filter-type-*`, `filter-confidence`, `filter-owner`
- Review/notes/conflicts: `btn-claim`, `btn-release`, `notes-input`, `conflicts-tab`
- Export: `btn-export-json`, `btn-export-coco-selection`
- CLI→UX handshake: run `python -m src.cli extract …` then verify UI markers and ability to `btn-load-pipeline-annos`

### Why this alignment helps
- Keeps UX, CLI, and pipeline stages in lock‑step using explicit selectors and commands the smokes verify.
- Reduces ambiguity: every user step maps to concrete artifacts (Stage 01→14) and a single, paved‑road CLI.
- Matches the Happy Path Guide so operators and contributors have one canonical flow.
