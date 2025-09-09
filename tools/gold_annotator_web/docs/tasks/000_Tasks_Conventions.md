# Tasks Conventions

Use these checklists to track UI interactions and expected screenshots. They are designed to survive /compact or restarts.

- [ ] Checkboxes: mark steps done as you progress.
- [ ] Screenshots: save to `tools/gold_annotator_web/docs/screenshots/<flow>/NN_name.png`.
- [ ] Ports/base URL: default `http://localhost:3002` unless you changed it.
- [ ] Variables: replace placeholders like `<DOC_NAME>` with your actual values.
- [ ] Puppeteer MCP: use the provided selectors as hints; adjust to match current UI if needed.

Screenshot naming convention

- `[flow]/NN_title.png`, where `flow` mirrors the checklist file number and topic.
- Examples:
  - `002_render/01_render_form.png`
  - `004_boxes/02_box_resized.png`

Artifacts and paths

- Images out dir: `tools/gold_annotator_web/data/images/<DOC_NAME>`
- Sample PDF: `tools/gold_annotator_web/data/input/pipeline/cleaned_BHT_CV32A65X_marked.pdf` (or your own)
- Boxes JSON: `.../<DOC_NAME>/<DOC_NAME>.boxes.json`
- Exported PDF: `.../<DOC_NAME>/<DOC_NAME>_annotated.pdf`

Puppeteer MCP quick hints

- Navigate: goto base URL (e.g., `/`).
- Fill inputs: prefer `[name=...]` or placeholder labels; fallback to `text=` queries.
- Click buttons: `button:has-text("Label")` or role-based queries.
- Canvas interactions: simulate mouse down/move/up with offsets on the overlay canvas.
