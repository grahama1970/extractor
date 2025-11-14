# Fix Stage 09a gutters (visible fill + plaques) so annotated PDFs show context

## Repository and branch

- **Repo:** `grahama1970/extractor`
- **Branch:** `feature/extractor-sanity-refactor`
- **Paths of interest:**
  - `src/extractor/pipeline/steps/09a_pdf_annotator.py`
  - `data/results/pipeline/09a_pdf_annotator/annotated.pdf`
  - `scripts/artifacts/annot_preview_request-1.png` vs `scripts/artifacts/annot_preview_request-1-1.png`

## Summary

The Stage 09a overlay still renders gutters with barely-visible fills and silently drops plaques when the per-page tab quota is exceeded. Even after our recent tweaks, operators (and clients) only see thick red rectangles and column guides—no labels. The latest PNG we generated (`annot_preview_request-1-1.png`, sha256 `5351de5ad431ee97eb2bbdb2f71ecb4adc9d0ae963bb0a77537c4e66927bda7b`) still looks blank in the gutters because:

1. We draw the pastel gutter fill *behind* the column grid overlay, so it remains indistinguishable when zoomed out.
2. `_draw_gutter_tag` is skipped whenever `MAX_TABS_PER_PAGE` is breached, meaning busy pages never show “Section/Table” plaques.
3. The right-side "T" endcaps inherit the same low-contrast styling, so the canvas edges look empty even when sections exist.

We need Copilot to do a proper pass that: (a) guarantees a bold gutter layer above the grid, (b) forces labels regardless of overflow, and (c) keeps the artifacts deterministic.

## Objectives

1. **Gutter rendering order & style**
   - Draw gutter lanes *after* the column grid/highlight overlays so the fill and border remain visible.
   - Increase contrast (fill + border) and consider adding a subtle drop shadow so the lane reads at 100% zoom.
2. **Always-on plaques**
   - Remove/relax the `MAX_TABS_PER_PAGE` guard so every overlay gets a left-lane plaque, shrinking the font as needed.
   - Ensure text color stays readable (no white-on-white) and connectors land inside the overlay, not under the column guides.
3. **Section markers on right lane**
   - Guarantee `kind == "section"` overlays render a clear right-lane marker (either the existing T-endcap or a new badge) even when the column grid is visible.
4. **Artifact proof**
   - Re-run Stage 09a with the standard BHT input so `data/results/pipeline/09a_pdf_annotator/annotated.pdf` and `scripts/artifacts/annot_preview_request-*.png` show obvious gutters + labels.

## Constraints for the patch

- Keep Stage 09a deterministic; do not introduce randomness in plaque placement.
- Preserve existing CLI surface (`python -m extractor.pipeline.steps.09a_pdf_annotator`). Add knobs only if absolutely required.
- No external assets; stick to PyMuPDF drawing APIs already imported.
- Update/add unit or smoke coverage only if it helps guard the new behavior (optional but encouraged).
- Provide a brief `TESTING.md` entry or doc note if new knobs are introduced.

## Acceptance criteria

1. Running Stage 09a with the current inputs (`data/input/pipeline/BHT_CV32A65X_with_requirements_noannots_clean.pdf`, etc.) produces an annotated PDF whose gutters clearly show labeled plaques on page 1 (and other populated pages) at 100% zoom.
2. `scripts/artifacts/annot_preview_request-*.png` (regenerated via `pdftoppm`) visibly show the gutter fill + text—no more "blank" strips.
3. `_draw_gutter_tag` never silently skips tags due to overflow; if plaques need to compress, they shrink gracefully but stay legible.
4. Right-hand section markers are present for every section overlay, even with column grids enabled.
5. No regressions to table/figure callouts or section plaques (existing overlays still render as before).

## Test plan

1. **Regenerate Stage 09a**
   ```bash
   source .venv/bin/activate && \
   set -a && [ -f .env ] && source .env && set +a && \
   python -m extractor.pipeline.steps.09a_pdf_annotator \
     data/input/pipeline/BHT_CV32A65X_with_requirements_noannots_clean.pdf \
     data/results/pipeline/04_section_builder/json_output/04_sections.json \
     data/results/pipeline/05_table_extractor/json_output/05_tables.json \
     data/results/pipeline/06_figure_extractor/json_output/06_figures.json \
     --reflowed-json data/results/pipeline/07_reflow_section/json_output/07_reflowed.json
   ```
2. Rasterize page 1:
   ```bash
   pdftoppm -f 1 -l 1 -png data/results/pipeline/09a_pdf_annotator/annotated.pdf \
     scripts/artifacts/annot_preview_request-1
   ```
3. Visually inspect the PNG (or PDF) at 100% zoom—plaque text must be obvious on both gutters.
4. Optional: spot-check several other pages to ensure no overflow or text clipping.

## Implementation notes

- `_draw_page_gutter_side`, `_draw_gutter_tag`, `_draw_vertical_tabs`, and the overlay loop (~line 1180) are the primary touch points.
- Consider drawing the column grid first, then the gutters, then plaques, then overlays.
- If the current per-page tab limit causes perf issues, add a fallback (e.g., stack plaques vertically) instead of dropping them entirely.
- The artifacts live under `data/results/pipeline/09a_pdf_annotator/` and `scripts/artifacts/`; please include updated screenshots/logs with the PR.

## Clarifying questions

1. Are you OK with increasing the PDF size slightly (a few KB) due to thicker gutter fills?
2. Should we expose a CLI flag to toggle gutter rendering order, or just hardcode the new behavior?
3. Do we need to restyle the column grid itself (e.g., fade it more) while we’re here?
