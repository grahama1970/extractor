# Tabbed Prototypes — Restore Status

Scope: `prototypes/tabbed/html`

Status: restored and runnable (dev), matching the “Classic Three‑Panel Layout” screenshot closely. Key features:

- Classic layout with left Explorer, center canvas + HUD, right Inspector
- Thumbnail rail (left) or filmstrip (bottom) with smooth paging
- Sticky header and working pager with zoom
- Box draw/resize/move with snap, keyboard nudge, duplicate/delete
- Label management dialog and persisted custom labels
- Build chip in UI showing git/time; dev/preview send `no-store` headers

Notable implementation notes:

- Added `src/lib/utils.ts` (shadcn `cn` helper)
- Added `src/lib/pdf.ts` (PDF.js glue: load, canvas render, thumbnail render)
- Public worker: `public/pdf.worker.min.js` (served at `/pdf.worker.min.js`)
- Graceful fallback: if `/bht.pdf` is missing, canvases render a placeholder so the UI remains functional

How to run (local):

1. Backend (optional, for API proxy): `python -m uvicorn extractor.core.scripts.server:app --host 0.0.0.0 --port 8001` (or 8000 if 8001 is in use)
2. Frontend (workspace install at parent):
   - One-time install at parent: `cd prototypes/tabbed && npm install`
   - Dev server: `VITE_API_PROXY=http://127.0.0.1:8001 npm run -w html dev -- --force`
3. Open `http://127.0.0.1:8080/classic` or `/main`

VS Code tasks (single-step):

- Default: `Dev: Clean + Backend(8001) + Vite(8080)` — installs (if needed), then starts FastAPI on :8001 (auto‑fallback to :8000 if :8001 is busy) and Vite on :8080 (workspace-aware)
- Also available: `Run Backend + Dev (Auto)` — equivalent single-step runner

Verification quick check:

- Header shows “Classic Three‑Panel Layout”
- Explorer panel has “Open PDF”, “Search files”, file list, “Export All”
- Center canvas scrolls; boxes draw and drag with snap
- Bottom pager updates page label; thumbs selectable (left/bottom)
- Inspector updates `Label Type`, `Instance ID`, and `Generate JSON` opens a dialog

Next steps (optional):

- Add a small two‑page sample PDF as `public/bht.pdf` if you prefer a real render instead of the placeholder
- Wire the left “Open PDF” to pick local/server PDFs
- Expand Puppeteer checks to assert sticky toolbars + non‑blocking overlay wheel
