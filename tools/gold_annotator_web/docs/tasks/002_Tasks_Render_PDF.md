# 002 — Render PDF to Images

Goal: rasterize a PDF into page images under `data/images/<DOC_NAME>`.

- [ ] Open homepage at base URL.
- [ ] Locate “Render PDF” controls.
- [ ] Fill PDF path: `data/input/pipeline/cleaned_BHT_CV32A65X_marked.pdf` (or your file).
- [ ] Fill Out dir: `data/images/<DOC_NAME>`.
- [ ] Click Render.
- [ ] Wait for completion message/toast.
- [ ] Verify out dir contains images (e.g., `page_0001.png`).
- [ ] Screenshot: `docs/screenshots/002_render/01_render_form.png` (before submit).
- [ ] Screenshot: `docs/screenshots/002_render/02_after_render.png` (after success).

Hints for Puppeteer MCP

- [ ] `goto /`
- [ ] `fill [name=pdfPath]` with the PDF path (adjust selector to UI).
- [ ] `fill [name=outDir]` with the output folder.
- [ ] `click button:has-text("Render")`
- [ ] `screenshot 002_render/02_after_render.png`
