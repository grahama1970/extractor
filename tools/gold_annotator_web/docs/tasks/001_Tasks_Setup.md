# 001 — Setup and Sanity

- [ ] Ensure Node and Python available (Node 18+, Python 3.9+).
- [ ] Install JS deps: `npm i` in `tools/gold_annotator_web`.
- [ ] Ensure Python deps installed (e.g., `pip install pymupdf`).
- [ ] Confirm sample PDF exists or place your own under `data/input/pipeline/`.
- [ ] Start dev server: `npm run dev` (expect `http://localhost:3002`).
- [ ] Verify landing page renders.
- [ ] Screenshot: `docs/screenshots/001_setup/01_home.png`.

Optional environment checks

- [ ] Confirm `/api/pdf-worker` returns a JS worker bundle.
- [ ] Confirm `/api/list?dir=data/images` works (empty is OK initially).
