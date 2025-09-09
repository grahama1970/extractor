# 012 — API Endpoints Smoke Test

Goal: confirm key backend routes respond as expected.

- [ ] `/api/list?dir=data/images` returns an array of docs.
- [ ] `/api/pdf?path=data/input/pipeline/<your.pdf>` streams the PDF.
- [ ] `/api/pdf-worker` returns a JS worker bundle.
- [ ] `/api/render` (POST with JSON: `{ pdfPath, outDir }`) creates images.
- [ ] `/api/boxes` (GET/POST) loads/saves `*.boxes.json`.
- [ ] `/api/crop` returns base64 PNG for a region.
- [ ] `/api/extract-table` returns table JSON (requires model or paste fallback).
- [ ] `/api/export-annotated` creates `<DOC_NAME>_annotated.pdf`.
- [ ] `/api/save` persists a gold JSON payload to `expected_json` path.
- [ ] `/api/suggest` responds with heuristics for type/json path.

Screenshots (optional)

- [ ] `docs/screenshots/012_api/01_list.png`
- [ ] `docs/screenshots/012_api/02_boxes_get.png`

Notes

- Use a REST client or `curl` to exercise endpoints directly.
- Some routes shell out to Python (`python3`); ensure deps are available.
