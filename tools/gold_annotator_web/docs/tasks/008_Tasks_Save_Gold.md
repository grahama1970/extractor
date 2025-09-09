# 008 — Save Gold JSON

Goal: persist the gold label JSON to a path and verify content.

- [ ] With a box selected and `expected_json` prepared (from Extract or manual paste), click “Save Gold”.
- [ ] Confirm the file is written to the specified JSON path.
- [ ] Screenshot: `docs/screenshots/008_save_gold/01_gold_saved.png`.
- [ ] Open the JSON file on disk to verify content structure.
- [ ] Screenshot: `docs/screenshots/008_save_gold/02_gold_file_content.png` (optional).

Hints for Puppeteer MCP

- [ ] Prefer clicking Save Gold from inline HUD or a global control if available.
- [ ] Validate via `/api/pdf?path=<json_path>` only if serving JSON is supported; otherwise, verify via filesystem.

