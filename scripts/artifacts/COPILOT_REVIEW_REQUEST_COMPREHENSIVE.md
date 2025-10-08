Fork: grahama1970/extractor
Branch: feat/pdfplumber-numeric-audit
Path: git@github.com:grahama1970/extractor.git#feat/pdfplumber-numeric-audit

Comprehensive Review Request

Context
- We’re shipping an “alpha+” loop tomorrow:
  1) Upload PDF in the UI.
  2) Pipeline runs with progress; machine annotations produced.
  3) Human edits/moves/adds boxes; save curated gold.
  4) Background training updates calibrator; optional approval gate.
  5) Export curated document to ArangoDB; background FAISS-KNN + LLM rationale.

Live features & scenarios/
- prototypes/tabbed/html (UI) → ui_pipeline.js wires upload/run/status/progress, annotations, merged preview, export, training.
- prototypes/tabbed/api/server.py (FastAPI) → upload, run, progress, annotations, merged, export, train+approve.
- scripts/export/export_arango.py → implemented real Arango writer with curated overlay.
- src/extractor/pipeline/steps/* → deterministic + curated ingestion and overlay.

What to review
- System risks (race conditions, partial writes, missing locks).
- API consistency (params, payload shapes, error semantics).
- Determinism (PIPELINE_DETERMINISTIC=1) threading across 01/03/06/07.
- Curated overlay: correctness, id matching, side effects.
- Exporter: idempotency of upserts; minimal indexes; edge construction.

Clarifying questions
1) Should exporter write an explicit export manifest with content hash (added) and edge counts sufficient for CI gates?
2) Do you prefer overlay at export only vs. overlay baked into Stage 07 unified document (we added metadata flags; data already merged in memory)?
3) Any additional fields expected by downstream consumers (e.g., captions, table headers) that should be lifted into Arango now?

Please deliver
- Prioritized issue list with unified diffs of proposed changes.
- Suggested acceptance tests or smokes to harden regressions.

Key relative paths to inspect
- prototypes/tabbed/api/server.py
- prototypes/tabbed/html/src/ui_pipeline.js
- scripts/export/export_arango.py
- src/extractor/pipeline/steps/01_annotation_processor.py
- src/extractor/pipeline/steps/03_suspicious_headers.py
- src/extractor/pipeline/steps/06_figure_extractor.py
- src/extractor/pipeline/steps/07_reflow_section.py
- src/extractor/pipeline/run_all.py

