Context: 09a Visual Integrity + 09b Audit Digest
Date: 2025-11-14

Scope
- Harden Stage 09a overlays so auditors can visually verify sections/tables/figures without guessing what the colors mean.
- Keep the 09b audit authoritative (zero warnings) while still flagging multi-page table merges.
- Ensure downstream reviewers have both the annotated PDF and the preview PNG paths in every run so collaboration stays visual-first.

Current Status (2025-11-14)
1. 09a overlay renderer (`src/extractor/pipeline/steps/09a_pdf_annotator.py`)
   - Gutters are back: left rail shows semantic labels, right rail shows section endcaps.
   - Section headers have their own overlays and plaques, proving Stage 04 IDs flow through.
   - Table overlays pull Stage 07 rows/headers into the PDF so reviewers see the extracted data without opening JSON.
   - Figures now render the LLM caption (or an explicit “unavailable” notice) inside the overlay.
   - Annotated PDF regenerated at `data/results/pipeline/09a_pdf_annotator/annotated.pdf`; preview PNG refreshed under `data/results/pipeline/09b_audit/previews/`.
2. 09b audit (`data/results/pipeline/09b_audit/json_output/09b_audit.json`)
   - Still passes with 0 errors / 0 warnings, but records the two logical table merges (`lt_b216dfd584`, `lt_081135eae9`).
   - Serves as the single “expected results” manifest for this BHT PDF.

Known Issues
- Multi-page table `lt_081135eae9` (pages 4–5) still appears as a merged group. Audit only enforces contiguity, so we need a semantic check to prove the merge is intentional.
- Figure captions rely on cached AI descriptions; when running fully offline we fall back to “unavailable,” which is acceptable but not ideal for UX reviews.

Verification Steps
```bash
source .venv/bin/activate && \
set -a && [ -f .env ] && source .env && set +a && \
python -m extractor.pipeline \
  --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots_clean.pdf \
  --out data/results/pipeline \
  --stop-on-fail
```
Artifacts to review:
- Annotated PDF: `data/results/pipeline/09a_pdf_annotator/annotated.pdf`
- Preview PNG: `data/results/pipeline/09b_audit/previews/annotated_preview_page1.png`
- Audit JSON: `data/results/pipeline/09b_audit/json_output/09b_audit.json`

Next Steps
1. Diagnose the lt_081135eae9 merge by tracing Stage 07’s `tables[*].normalized_id` and confirming whether two physically separate tables get collapsed. Add a semantic guardrail (e.g., require identical headers or `continued=True`).
2. Decide how to persist figure captions when the SciLLM router is offline (cache, mock data, or queued re-run) so auditors never see the “unavailable” placeholder.
3. Layer a Markdown digest generator on top of `09b_audit.json` so humans receive the same top-line metrics you summarized manually.
