# Simplify 09a overlays and walkthrough clarity

## Repository and branch
- **Repo:** experiments/extractor
- **Branch:** feature/annotator-cleanup
- **Paths:**
  - `src/extractor/pipeline/steps/05_table_extractor.py`
  - `src/extractor/pipeline/run_pipeline.py`
  - `src/extractor/pipeline/steps/09a_pdf_annotator.py`
  - `walkthrough.md`

## Summary
- Stage 05 dedupe bug fixed; sticky lattice strategy uses last good lattice only; final IOU guard removes overlaps.
- Run pipeline calls 09a with gutter/columns disabled for clean overlays.
- 09a overlays are stroke-only (no fills), per-kind bbox origin (tables bottom-left, others top-left), thicker strokes; gutters/tabs removed.
- Walkthrough updated to match latest run; per-page ordering; clean images without tint.

## Objectives
1. Ensure outlines for section/figure/table render in correct positions without fills or side gutters.
2. Keep table dedupe stable (IOU >= 0.70) with last-good lattice preference.
3. Walkthrough stays deterministic and mirrors latest artifacts (page ordering and descriptions).

## Constraints
- Do not reintroduce fills/watermarks/gutters in 09a.
- Keep existing pipeline stage outputs and counts unchanged (tables=6, figure=1, requirements=1 on fixture).
- No new dependencies.

## Test plan
1. Full pipeline with requirements:
   ```bash
   PYTHONPATH=$(pwd)/src \
   python -m extractor.pipeline.run_pipeline \
     --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
     --out data/results/latest_run \
     --extract-requirements
   ```
2. Export previews:
   ```bash
   pdftoppm data/results/latest_run/09a_pdf_annotator/annotated.pdf \
     scripts/artifacts/annotated_latest -png
   ```
3. Verify `scripts/artifacts/annotated_latest-1.png`:
   - Section outline at header; table/figure outlines around their objects.
   - No colored gutters/bands; no duplicate figure text.
4. Confirm `walkthrough.md` references the latest images and ordering (S1 → F1 → T1 on page 1).

## Acceptance criteria
- Page 1 outlines visible and aligned; no tinted fills or side gutters.
- Table dedupe yields 6 unique tables on fixture.
- Walkthrough renders without extra badges/overlays beyond the embedded annotated PNG.

## Clarifying questions
1. Do we also want SVG connectors between data pane items and PDF overlays, or keep the clean image only?
2. Preferred stroke color/width for outlines? (Current: ~2.5pt, stroke-only, kind colors.)
