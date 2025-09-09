# Unified Tasks Checklist (000–013)

Single, end‑to‑end checklist consolidating all task files. Check items as you complete them. Screenshot paths follow the existing convention under `tools/gold_annotator_web/docs/screenshots/<flow>/NN_name.png`.

<!-- progress:start -->
Progress: 0/73 (0%) [........................................]
<!-- progress:end -->

Quick refs

- Base URL: `http://localhost:3002`
- Images out dir: `data/images/<DOC_NAME>`
- Sample PDF: `data/input/pipeline/cleaned_BHT_CV32A65X_marked.pdf`
- Boxes JSON: `.../<DOC_NAME>/<DOC_NAME>.boxes.json`
- Annotated PDF: `.../<DOC_NAME>/<DOC_NAME>_annotated.pdf`

## 001 — Setup and Sanity

- [ ] Node 18+ and Python 3.9+ installed.
- [ ] JS deps installed: `npm i` in `tools/gold_annotator_web`.
- [ ] Python deps installed (e.g., `pip install pymupdf`).
- [ ] Sample PDF present under `data/input/pipeline/` (or your own).
- [ ] Dev server running: `npm run dev` (expect `http://localhost:3002`).
- [ ] Landing page renders. Screenshot: `001_setup/01_home.png`.
- [ ] `/api/pdf-worker` returns a worker bundle.
- [ ] `/api/list?dir=data/images` responds (empty OK).
- [ ] Lint and types pass: `npm run lint` and `npm run type-check` (if configured).
  - Optional: Add a brief ADR in `docs/` capturing stack choices.

## 002 — Render PDF to Images

Goal: rasterize pages to `data/images/<DOC_NAME>`.

- [ ] Open homepage.
- [ ] Fill PDF path: `data/input/pipeline/cleaned_BHT_CV32A65X_marked.pdf` (or your file).
- [ ] Fill Out dir: `data/images/<DOC_NAME>`.
- [ ] Click Render; wait for success toast.
- [ ] Out dir contains images (e.g., `page_0001.png`).
- [ ] Screenshots: `002_render/01_render_form.png`, `002_render/02_after_render.png`.
  - Acceptance: Large PDFs (if available) render without errors; app remains responsive.

## 003 — Open and Navigate Document

- [ ] Click “Load PDF”.
- [ ] Set images dir: `data/images/<DOC_NAME>`.
- [ ] Page renders in viewer.
- [ ] Navigate next/prev via buttons or shortcuts.
- [ ] Screenshots: `003_navigate/01_first_page.png`, `003_navigate/02_next_page.png`.
  - Acceptance: Keyboard nav (`[`, `]`, PageUp/Down) works; last page restores after reload.

## 004 — Draw and Edit Boxes

- [ ] Draw a box by click‑drag on overlay.
- [ ] Screenshot: `004_boxes/01_box_drawn.png`.
- [ ] Move selected box; screenshot: `004_boxes/02_box_moved.png`.
- [ ] Resize via handle; screenshot: `004_boxes/03_box_resized.png`.
- [ ] Delete with Backspace/Delete (ESC clears selection). Screenshot: `004_boxes/04_box_deleted.png`.
  - Acceptance: Box operations remain accurate at different zoom levels (no coordinate drift).

## 005 — Side Pane Actions (HUD optional)

- [ ] Draw/select a box.
- [ ] In side pane, set ID, Type, JSON path.
- [ ] Click “Save Gold”; confirm file written.
- [ ] Click “Auto‑label”; confirm type/path updated if suggested.
- [ ] Click “Crop” to open a preview.
- [ ] For tables, click “Extract”; rows/columns populate if available.
  - Acceptance: If a JSON schema is present for Gold output, validate against it; otherwise ensure structure matches examples.

## 006 — Save and Reload Boxes

- [ ] Click “Save Boxes”.
- [ ] `.boxes.json` written under `data/images/<DOC_NAME>/`.
- [ ] Screenshot: `006_save_boxes/01_after_save.png`.
- [ ] Reload or switch away/back; boxes reload automatically.
- [ ] Screenshot: `006_save_boxes/02_reloaded_boxes.png`.
  - Acceptance: Malformed `.boxes.json` is reported with a user-visible error; app does not crash.

## 007 — Crop and Extract Content

- [ ] Select a box with text/table.
- [ ] Click Crop; cropped PNG shown. Screenshot: `007_crop_extract/01_cropped.png`.
- [ ] Click Extract; get text/table JSON or paste fallback. Screenshot: `007_crop_extract/02_extract_result.png`.
  - Acceptance: Extraction failures surface clear messages; UI stays usable.

## 008 — Save Gold JSON

- [ ] With expected JSON prepared (from Extract or manual), click “Save Gold”.
- [ ] File written to configured path.
- [ ] Screenshots: `008_save_gold/01_gold_saved.png`, `008_save_gold/02_gold_file_content.png` (optional).
  - Acceptance: Saved JSON has expected keys/types, or validates against schema if present.

## 009 — Suggest / Auto‑label

- [ ] Select a box; click “Auto‑label”.
- [ ] Observe inferred Type and JSON path.
- [ ] Screenshots: `009_suggest/01_after_autolabel.png`, `009_suggest/02_corrections.png` (optional).

## 010 — Export Annotated PDF

- [ ] Ensure boxes are saved.
- [ ] Click “Export Annotated PDF”; note output file path.
- [ ] Screenshots: `010_export/01_export_triggered.png`, `010_export/02_annotated_preview.png`.

## 011 — Keyboard Shortcuts

- [ ] Type shortcuts (e.g., `f` field, `t` table) work. Screenshot: `011_shortcuts/01_type_shortcut.png`.
- [ ] Save shortcut (e.g., `Ctrl/Cmd+S`) works. Screenshot: `011_shortcuts/02_save_shortcut.png`.
- [ ] Navigation shortcuts (e.g., `[` and `]`) work. Screenshot: `011_shortcuts/03_nav_shortcuts.png`.
  - Acceptance: Browser defaults (e.g., Cmd/Ctrl+W/R) do not interfere with core actions.

## 012 — API Endpoints Smoke Test

- [ ] `/api/list?dir=data/images` returns docs.
- [ ] `/api/pdf?path=...` streams PDF.
- [ ] `/api/pdf-worker` returns worker bundle.
- [ ] `/api/render` (POST `{ pdfPath, outDir }`) creates images.
- [ ] `/api/boxes` GET/POST round‑trips boxes JSON.
- [ ] `/api/crop` returns base64 PNG.
- [ ] `/api/extract-table` returns table JSON (or UI provides paste fallback).
- [ ] `/api/export-annotated` creates annotated PDF.
- [ ] `/api/save` persists gold JSON payload.
- [ ] `/api/suggest` returns heuristics for type/json path.
  - Acceptance: Endpoints return expected HTTP status codes on success and structured error JSON for invalid inputs.

## 013 — Screenshots Summary (Optional)

- [ ] 001_setup: `01_home.png`
- [ ] 002_render: `01_render_form.png`, `02_after_render.png`
- [ ] 003_navigate: `01_first_page.png`, `02_next_page.png`
- [ ] 004_boxes: `01_box_drawn.png`, `02_box_moved.png`, `03_box_resized.png`, `04_box_deleted.png`
- [ ] 005_hud: `01_hud_visible.png`, `02_id_type_json.png`, `03_auto_label.png`, `04_crop_preview.png`, `05_extract_result.png`
- [ ] 006_save_boxes: `01_after_save.png`, `02_reloaded_boxes.png`
- [ ] 007_crop_extract: `01_cropped.png`, `02_extract_result.png`
- [ ] 008_save_gold: `01_gold_saved.png`, `02_gold_file_content.png`
- [ ] 009_suggest: `01_after_autolabel.png`, `02_corrections.png`
- [ ] 010_export: `01_export_triggered.png`, `02_annotated_preview.png`
- [ ] 011_shortcuts: `01_type_shortcut.png`, `02_save_shortcut.png`, `03_nav_shortcuts.png`
- [ ] 012_api: `01_list.png`, `02_boxes_get.png`

---

Notes

- See `000_Tasks_List.md` for development phases, acceptance criteria, and open questions.
- Use automation selectors noted in individual task files if scripting E2E flows.
