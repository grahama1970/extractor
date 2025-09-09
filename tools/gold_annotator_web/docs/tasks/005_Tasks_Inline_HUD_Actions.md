# 005 — Side Pane Actions (HUD optional)

Goal: use the side pane to edit and run actions without blocking the canvas. The floating HUD is disabled by default to avoid occluding the selection; enable it only if desired.

- [ ] Draw/select a box (HUD stays hidden by default).
- [ ] In the side pane, set ID, Type, and JSON path.
- [ ] Click “Save Gold”; confirm file written.
- [ ] Click “Auto-label”; confirm type/path updates if suggested.
- [ ] Click “Crop” to open a cropped preview in a new tab.
- [ ] For tables, click “Extract”; if a table is returned, Columns/Rows fields populate.

Notes

- Use `[data-testid=save-gold-btn]`, `[data-testid=auto-label-btn]`, `[data-testid=crop-btn]`, `[data-testid=extract-btn]` in automation.
- Press Escape to clear selection. Press Delete/Backspace to remove the current box.
