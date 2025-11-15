Context: Stage 09a gutter regression + Copilot escalation
Date: 2025-11-14 (afternoon)

Scope
- Re-establish clear gutters/plaques in `09a_pdf_annotator.py` so auditors see section/table labels without zoom gymnastics.
- Keep Stage 09b audit untouched while we focus on the visual regression.
- Capture the problem precisely for Copilot (request logged under `src/extractor/pipeline/docs/COPILOT_REVIEW_REQUEST_2025-11-14_gutter.md`).

Current Status
1. `feature/extractor-sanity-refactor` carries the gutter tweaks (stronger fills + plaque autosizing) but **artifacts still look blank** at 100% zoom because column guides are drawn above the gutters and plaques are skipped on overflow. The latest PNGs are:
   - Old render: `scripts/artifacts/annot_preview_request-1.png`
   - New render: `scripts/artifacts/annot_preview_request-1-1.png` (sha256 `5351de5a...da7b`)
   Users report no visible difference, so the change is ineffective.
2. Copilot review request has been committed documenting the issue and desired fix. Waiting on review because DNS hiccups blocked the initial push (manual push completed afterward).
3. Stage 09b audit (`data/results/pipeline/09b_audit/json_output/09b_audit.json`) still reports zero warnings; no additional work there yet.

Known Issues / Gaps
- Gutters draw behind the grid overlay; plaques disappear whenever `MAX_TABS_PER_PAGE` is exceeded.
- Operators rightly distrust the artifacts because they can’t see labels even though the code says they exist.
- Multi-page table merge (`lt_081135eae9`) remains unresolved but is deprioritized until the gutter fix lands.

Verification Steps (repeatable repro)
```bash
source .venv/bin/activate && \
set -a && [ -f .env ] && source .env && set +a && \
python -m extractor.pipeline.steps.09a_pdf_annotator \
  data/input/pipeline/BHT_CV32A65X_with_requirements_noannots_clean.pdf \
  data/results/pipeline/04_section_builder/json_output/04_sections.json \
  data/results/pipeline/05_table_extractor/json_output/05_tables.json \
  data/results/pipeline/06_figure_extractor/json_output/06_figures.json \
  --reflowed-json data/results/pipeline/07_reflow_section/json_output/07_reflowed.json
pdftoppm -f 1 -l 1 -png data/results/pipeline/09a_pdf_annotator/annotated.pdf \
  scripts/artifacts/annot_preview_request-1
```
Artifacts to inspect:
- Annotated PDF: `data/results/pipeline/09a_pdf_annotator/annotated.pdf`
- New/old PNG pair: `scripts/artifacts/annot_preview_request-1.png` vs `scripts/artifacts/annot_preview_request-1-1.png`
- Copilot request doc: `src/extractor/pipeline/docs/COPILOT_REVIEW_REQUEST_2025-11-14_gutter.md`

Next Steps
1. Wait for Copilot/code review response on the gutter fix (or implement our own follow-up) to ensure gutters render above the grid and plaques never drop.
2. Once visuals are correct, revisit the multi-page table merge guardrail.
3. After fixes land, regenerate artifacts and attach them to the Copilot request so future reviewers can trust the visuals.
