Title: Alpha+ UX ↔ Extractor Pipeline Integration

Summary
- User loads a PDF in the UI, triggers extraction, monitors progress, edits annotations, and saves to ArangoDB. Background training updates models for the next PDF.

User Flow
- Load PDF → POST /api/pdf → returns {run_id, doc_id}.
- Progress bar → GET /api/run/progress?run_id=… (stage-based percent).
- When done → GET /api/annotations?run_id=… (sections/tables/figures bundle).
- Edit/confirm → POST /api/annotations/save {run_id, …} → writes data/runs/<run_id>/curated.json.
- Train (optional) → POST /api/train/start; poll /api/train/status.
- Export → POST /api/export/arango {run_id} → writes to ArangoDB; FAISS+LLM rationale runs in background.

Stage-01 Integration
- Stage 01 now ingests UX-curated annotations automatically when available.
- Detection order:
  - CLI: `--ux-curated-json path/to/curated.json`.
  - Auto: if `RUN_ID` is set and `data/runs/<RUN_ID>/curated.json` exists.
  - Fallback: extract from PDF annotations.
- Curated schema supported:
  - `{"annotations": [{"page": int, "original_rect": [x0,y0,x1,y1], …}]}`
  - `{"boxes_by_page": {"1": [{x,y,w,h,type,instanceId}]}}` (normalized 0..1); converted to PDF points.

VS Code Tasks
- `Dev: scripts/dev.sh (backend+vite)` → launches FastAPI on 8001 and Vite on 8080; runs a CDP console-error smoke automatically.
- `Run: Backend + Preview` → convenience runner if you prefer separate tasks.

Acceptance (Alpha+)
- Progress reaches 100% without console errors (Vite overlay absent).
- Annotations render; user can confirm/tag and save.
- Saving produces `data/runs/<run_id>/curated.json` and retriggered runs ingest curated when present.
- Export writes nodes/edges to ArangoDB; background clustering + rationale stubs launch (visible in logs).

Notes
- Deterministic mode: `PIPELINE_DETERMINISTIC=1` caps concurrency in figure extraction; does not disable required LLM stages.
- Models read from .env defaults; explicit `--model` overrides when exposed by CLIs.

