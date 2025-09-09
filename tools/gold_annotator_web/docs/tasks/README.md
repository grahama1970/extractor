# Gold Annotator — Tasks Index

Prefer the single unified checklist first: `00N_Tasks_Unified_Checklist.md`. For deeper context, see `000_Tasks_List.md`, then `000_Tasks_Conventions.md`.

Progress meter

- Auto-update the progress bar at the top of the unified checklist by running:
  - `python scripts/update_checklist_progress.py` (defaults to the unified file), or
  - `python scripts/update_checklist_progress.py tools/gold_annotator_web/docs/tasks/00N_Tasks_Unified_Checklist.md`

- 00N: Unified Checklist — `00N_Tasks_Unified_Checklist.md`
- 000: Master Backlog — `000_Tasks_List.md`
- 000b: Conventions — `000_Tasks_Conventions.md`
- 001: Setup — `001_Tasks_Setup.md`
- 002: Render PDF — `002_Tasks_Render_PDF.md`
- 003: Open/Navigate — `003_Tasks_Open_and_Navigate_Doc.md`
- 004: Boxes — `004_Tasks_Draw_and_Edit_Boxes.md`
- 005: Inline HUD — `005_Tasks_Inline_HUD_Actions.md`
- 006: Save Boxes — `006_Tasks_Save_Boxes.md`
- 007: Crop & Extract — `007_Tasks_Crop_and_Extract.md`
- 008: Save Gold — `008_Tasks_Save_Gold.md`
- 009: Suggest — `009_Tasks_Suggest_Autolabel.md`
- 010: Export Annotated — `010_Tasks_Export_Annotated.md`
- 011: Shortcuts — `011_Tasks_Keyboard_Shortcuts.md`
- 012: API Smoke — `012_Tasks_API_Endpoints.md`
- 013: Screenshots Summary — `013_Tasks_Screenshots_Summary.md`

Optional flow definitions for automation live under `tests/interactions`.

Note on Paths

- Images now default to `data/images/<DOC_NAME>` (configure with `IMAGES_ROOT`).
- Old `data/labelstudio/images` still works if it exists, but is deprecated.
