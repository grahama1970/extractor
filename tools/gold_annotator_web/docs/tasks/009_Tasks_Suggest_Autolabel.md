# 009 — Suggest / Auto-label

Goal: run suggestion heuristics to infer type and JSON path automatically.

- [ ] Select a box that clearly contains a field/table.
- [ ] Click “Auto-label” in the Inline HUD.
- [ ] Observe inferred Type and JSON path.
- [ ] Screenshot: `docs/screenshots/009_suggest/01_after_autolabel.png`.
- [ ] If suggestions look incorrect, edit and re-save; note discrepancies.
- [ ] Screenshot: `docs/screenshots/009_suggest/02_corrections.png` (optional).

Hints for Puppeteer MCP

- [ ] Ensure the HUD container is the active context when firing the click.
- [ ] Wait for any toast/indication that suggestion applied.

