# 003 — Open and Navigate Document

Goal: load the PDF in the viewer and confirm navigation.

- [ ] Ensure `data/labelstudio/images/<DOC_NAME>` exists from step 002.
- [ ] Click “Load PDF” after setting your PDF path.
- [ ] In the doc selector, set images dir: `data/images/<DOC_NAME>` (for overlays/saved boxes).
- [ ] Confirm page renders within the PDF/image viewer.
- [ ] Navigate to next/previous page using “Next”/“Prev” buttons or keyboard shortcuts.
- [ ] Screenshot: `docs/screenshots/003_navigate/01_first_page.png`.
- [ ] Screenshot: `docs/screenshots/003_navigate/02_next_page.png`.

Hints for Puppeteer MCP

- [ ] Use list API if needed: `/api/list?dir=data/images` to find `<DOC_NAME>`.
- [ ] Fill `[data-testid=doc-input]` with the images folder name.
- [ ] Click `[data-testid=page-next]` and `[data-testid=page-prev]` to paginate.
