# 004 — Draw and Edit Boxes

Goal: draw, move, resize, and delete annotation boxes on the overlay canvas.

- [ ] Ensure a page is visible in the viewer.
- [ ] Draw a new box by click-drag on the overlay.
- [ ] Screenshot: `docs/screenshots/004_boxes/01_box_drawn.png`.
- [ ] Select the box and move it; confirm it snaps/alignment guides if available.
- [ ] Screenshot: `docs/screenshots/004_boxes/02_box_moved.png`.
- [ ] Resize the box from a corner/edge handle.
- [ ] Screenshot: `docs/screenshots/004_boxes/03_box_resized.png`.
- [ ] Press Backspace/Delete to remove the selected box; confirm it disappears and the selection clears. Press Escape to dismiss selection without deleting.
- [ ] Screenshot: `docs/screenshots/004_boxes/04_box_deleted.png`.

Hints for Puppeteer MCP

- [ ] Identify the overlay canvas element (react-konva Stage); click-drag with mouse events.
- [ ] Use `page.mouse.move` + down/up with coordinates within the stage bounds.
- [ ] To resize, drag a handle if visible or simulate scale via drag on edges.
