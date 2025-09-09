# 006 — Save and Reload Boxes

Goal: persist box annotations to `*.boxes.json` and ensure they reload.

- [ ] With one or more boxes present, click “Save Boxes” (global control).
- [ ] Confirm a `.boxes.json` file is written under the doc folder (under `data/images/<DOC_NAME>/`).
- [ ] Screenshot: `docs/screenshots/006_save_boxes/01_after_save.png`.
- [ ] Reload the page or switch away and back to the same document.
- [ ] Confirm boxes reappear automatically (loaded from `/api/boxes`).
- [ ] Screenshot: `docs/screenshots/006_save_boxes/02_reloaded_boxes.png`.

Hints for Puppeteer MCP

- [ ] Click `button:has-text("Save Boxes")`.
- [ ] After reload, wait for network idle or a selector indicating loaded boxes.
