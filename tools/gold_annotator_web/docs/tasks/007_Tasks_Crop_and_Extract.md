# 007 — Crop and Extract Content

Goal: verify region cropping and content extraction from a selected box.

- [ ] Select a box around a region with text/table.
- [ ] Click Crop; verify a cropped PNG is returned or shown in a modal/new tab.
- [ ] Screenshot: `docs/screenshots/007_crop_extract/01_cropped.png`.
- [ ] Click Extract; for fields, expect extracted text; for tables, expect JSON rows/columns.
- [ ] If LLM model is not configured, paste example JSON/text into the provided area and apply.
- [ ] Screenshot: `docs/screenshots/007_crop_extract/02_extract_result.png`.

Hints for Puppeteer MCP

- [ ] Handle newly opened tab for crop preview if it spawns one.
- [ ] For extract JSON, locate textarea/input for pasted result and confirm Save/Apply.

