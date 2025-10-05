# Alpha+ Pipeline Loop (UX ↔ Extractor)

This feature recipe defines an end-to-end, alpha-ready loop that connects the UX to the Extractor pipeline and back-end training/export services.

## Goals
- User loads a PDF in the UX and triggers extraction.
- Backend runs the pipeline asynchronously and reports progress.
- Machine annotations (sections/tables/figures) appear in the UI for review.
- User edits/adds/deletes boxes and tags errors; “blessed” corrections are saved.
- Asynchronous training updates calibrators to improve future runs.
- User exports curated results to ArangoDB; FAISS-KNN + LLM-verified rationale runs in background.

## Endpoints (FastAPI)
- POST `/api/pdf` — upload PDF; returns `{ doc_id, run_id }`; starts pipeline in background.
- GET `/api/run/status?run_id=…` — manifest status: queued/running/completed/error.
- GET `/api/run/progress?run_id=…` — progress percent and stage presence.
- GET `/api/annotations?run_id=…` — returns sections/tables/figures lists.
- GET `/api/triage?object_type=table|section|figure|entity&run_id=…` — ELS-ranked triage items (multi-type); supports global fallback.
- POST `/api/annotations/save` — saves curated/blesed annotations for the run into `data/runs/<run_id>/curated.json`.
- POST `/api/train/start` — background export + train; promotion left to existing gates.
- GET  `/api/train/status` — training state.
- GET  `/api/calibrator/metrics` — reliability metrics for overlay.
- POST `/api/export/arango?run_id=…` — alpha export; runs clustering + rationale jobs in background.

## Files & Artifacts
- Uploads: `data/uploads/<filename>`
- Runs: `data/runs/<run_id>/`
  - `manifest.json` — `{ doc_id, run_id, pdf_path, status, timestamps }`
  - `stages/04_section_builder/json_output/04_sections.json`
  - `stages/05_table_extractor/json_output/05_tables.json`
  - `stages/06_figure_extractor/json_output/06_figures.json`
  - `triage/{tables,sections,figures}.json` with `{ generated_at, items[] }` and `doc_id, run_id` in each item.
  - `curated.json` — saved/blesed annotations.
- Global triage mirror: `data/results/pipeline/triage_queue/…`
- Label events: `annotation_events/events.jsonl` (submitLabel supports `error_tags`)
- Training models: `training/models/table_calibrator/<ver>/` and `…/current` symlink (future)

## UX Hooks (alpha)
- Index pipeline panel:
  - List PDFs → select
  - Run Pipeline → async run
  - Status → show status & start progress polling
  - Load Annotations → read counts via `/api/annotations`
  - Start Training → run export+train scripts
  - Export → ArangoDB (alpha writer stub)
- Minimal triage list shows ELS and reasons; Classic layout remains for label actions.

## Implementation Notes
- `doc_id`: `<normalized_basename>__<sha256_first8>`; embedded in triage items; env DOC_ID used as override.
- `run_id`: provided by server; env RUN_ID used by triage to write run-scoped queues.
- Table `numeric_recall` and `foreign_numeric_ratio` (Phase 1): page-level mapping computed in Stage 05 fusion `rank_features`.
- Parse thresholds: `conf/parse_thresholds.json` defines strict and grace modes.

## Next Iteration
- Replace export stub with real Arango writer (collections/edges).
- React-native triage route.
- Section-span–based numeric recall for tables (Phase 2).
- Learned ELS model loader (after ≥60 labeled samples).

Owner: alpha-pipeline
Status: active
