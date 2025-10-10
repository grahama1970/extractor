# Current Context — Extractor Pipeline (2025-10-09)

Repo: /home/graham/workspace/experiments/extractor
Focus: Stabilize pipeline on 2‑page PDF: prototypes/tabbed/pdfs/BHT CV32A65X.pdf

Decisions today
- Color enrichment moved to Stage 03 (suspicious headers) as opt‑in: STAGE03_COLOR_ENRICH=1
- Stage 04 keeps a skip-if-present color enrichment to avoid duplication (STAGE04_COLOR_ENRICH=1)
- .gitignore tightened (artifacts/, data/, memory/, screenshots/, tabbed pdfs/screenshots)

Key files touched
- src/extractor/pipeline/steps/03_suspicious_headers.py
  * Added optional color enrichment for target/above/below blocks via PyMuPDF span color
  * Prompt context already surfaces first_span_font.color_bucket when present
- src/extractor/pipeline/steps/04_section_builder.py
  * Added color enrichment utility, but now skips if Stage 03 already set color
- .gitignore updated to exclude heavy artifacts and local data

Intent
- Keep Stage 02 strictly Marker-only (policy intact)
- Use Stage 03’s vision context to improve header verification with real color signals
- Keep Stage 04 purely structural/visual capture; no duplicate color work when Stage 03 provided it

Immediate next actions
1) Run pipeline iteratively on BHT CV32A65X.pdf (Stages 02→03→04→05→06b→07→14)
2) If Stage 02 missing models, set OFFLINE_PDF_PREDICTORS=0 and correct Marker env; no PyMuPDF fallback allowed in Stage 02
3) Ensure .env LLM routing works for Stage 03 (vision) and Stage 07 (text/VLM) via LiteLLM

Copilot/Code Review plan
- After green local run, open a feature branch and push
- Prepare review prompt with context, scenarios, questions, and request unified diffs

