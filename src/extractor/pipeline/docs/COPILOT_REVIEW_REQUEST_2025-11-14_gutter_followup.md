# Stage 09a gutter follow-up: still no visible left-lane plaques

## Repository and branch

- **Repo:** `grahama1970/extractor`
- **Branch:** `feature/extractor-sanity-refactor`
- **Paths to inspect:**
  - `src/extractor/pipeline/steps/09a_pdf_annotator.py`
  - `data/results/pipeline/09a_pdf_annotator/annotated.pdf`
  - `scripts/artifacts/annot_preview_request-1-1.png`
  - `scripts/artifacts/annot_preview_request-1-1_gutter_zoom.png`

## Why this follow-up exists

We reapplied the large gutter/plaques patch verbatim (commit `23df800613a8e482deec6292c889b2fe6b8c874b`) and reran Stage 09a via:

```bash
source .venv/bin/activate && \
set -a && [ -f .env ] && source .env && set +a && \
python - <<'PY'
from pathlib import Path
from extractor.pipeline.steps import s09a_pdf_annotator as s09a
s09a.run(
    Path("data/input/pipeline/BHT_CV32A65X_with_requirements_noannots_clean.pdf"),
    Path("data/results/pipeline/04_section_builder/json_output/04_sections.json"),
    Path("data/results/pipeline/05_table_extractor/json_output/05_tables.json"),
    Path("data/results/pipeline/06_figure_extractor/json_output/06_figures.json"),
    reflowed_json=Path("data/results/pipeline/07_reflow_section/json_output/07_reflowed.json"),
    output_dir=Path("data/results/pipeline"),
)
PY
pdftoppm -f 1 -l 1 -png \
  data/results/pipeline/09a_pdf_annotator/annotated.pdf \
  scripts/artifacts/annot_preview_request-1
```

Artifacts were refreshed at 12:13 PT:

- PDF: `data/results/pipeline/09a_pdf_annotator/annotated.pdf`
- Page 1 PNG: `scripts/artifacts/annot_preview_request-1-1.png` (sha256 `5351de5a…bda7b`)
- Cropped gutter zoom: `scripts/artifacts/annot_preview_request-1-1_gutter_zoom.png`

Despite this, **there is still no discernible text in the left gutter**. Even when zooming to 200% (see the gutter zoom PNG), the lane shows only the pastel fill plus a few cyan vertical strokes—no plaques, no labels, no connectors. OCR against the gutter strip returns gibberish or empty strings. Operators continue to see “blank” gutters, defeating the purpose of the entire overlay layer.

## What we need Copilot to fix (again)

1. **Guarantee actual glyphs land in the gutter layer**
   - `_draw_gutter_tag` should produce dark text and connector lines whose RGB sum is < 300 so they survive rasterization.
   - Render plaques **after** every grid/column annotation and force `overlay=True`.
2. **Add automated verification**
   - Provide a lightweight image-based smoke (e.g., compare histogram or detect text) to ensure at least N dark pixels exist inside the left gutter rectangle for every touched page.
3. **Update artifacts**
   - Re-run Stage 09a + `pdftoppm` and attach a new PNG where plaques are visibly legible at 100% zoom.

## Acceptance criteria

1. `scripts/artifacts/annot_preview_request-1-1.png` must clearly show plaque rectangles and readable text within the left gutter at 100% zoom.
2. Left gutter text color/layering must differ enough from the background that OCR (`tesseract … --psm 6`) returns the actual Section/Table labels.
3. Column/grid overlays can never overpaint the gutter layer (add a unit or integration guard if needed).
4. The automated verification mentioned above runs in CI (or at least as a scripted smoke) and fails when the gutter is blank.

## Test plan (expected from Copilot)

1. Re-run Stage 09a and regenerate PNGs as shown above.
2. Add a script (or extend an existing smoke) that samples the gutter pixels and asserts a minimum contrast threshold.
3. Attach the updated PDF/PNG pair plus the verification script output to the PR.

Please treat this as a fresh request—the current artifacts demonstrably fail to show any left-gutter text.
