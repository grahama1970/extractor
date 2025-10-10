# Current Context — Extractor Pipeline (2025-10-10)

Repo: /home/graham/workspace/experiments/extractor
Branch: feat/walking-skeleton-pipeline (pushed)
Focus: Working “walking skeleton” pipeline on 2‑page PDF: prototypes/tabbed/pdfs/BHT CV32A65X.pdf

What landed today
- New branch feat/walking-skeleton-pipeline
- .gitignore tightened (data/results/, artifacts/, memory/, screenshots/, tabbed pdfs/screenshots)
- Stage 06 caps figures per doc via FIGURE_MAX_PER_DOC (default 12)
- Stage 06c PDF annotator added (draws boxes for sections/tables/figures)
- Scripts:
  - scripts/preflight_pipeline.sh (Ghostscript, PyMuPDF, Camelot, CHUTES env)
  - scripts/run_walking_skeleton.sh (01→14 minimal flow)

Key files touched
- src/extractor/pipeline/steps/06_figure_extractor.py: cap total figures processed per doc
- src/extractor/pipeline/steps/06c_pdf_annotator.py: new deterministic annotator
- scripts/preflight_pipeline.sh: environment/tooling preflight
- scripts/run_walking_skeleton.sh: orchestrates walking-skeleton run
- .gitignore: excludes heavy local outputs

Intent
- Keep Stage 02 strictly Marker-only (policy intact)
- Keep Stage 07 deterministic by default (images off via env); rely on existing strict JSON path
- Preserve Stage 05 LLM header-assist for low-confidence tables (length-preserving)

How to run (walking skeleton)
```bash
source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a
CHUTES_API_BASE=$CHUTES_API_BASE CHUTES_API_KEY=$CHUTES_API_KEY \
scripts/run_walking_skeleton.sh \
  "prototypes/tabbed/pdfs/BHT CV32A65X.pdf" \
  "data/results/pipeline"
```

Environment notes
- Set CHUTES_API_BASE and CHUTES_API_KEY (mapped to OPENAI_* automatically)
- Control figure load with FIGURE_MAX_PER_DOC (default 12)
- Stage 07 defaults: STAGE07_ATTACH_SECTION_IMAGE=0, STAGE07_INCLUDE_FIGURES=0 in the skeleton script

Review plan
- Open PR from feat/walking-skeleton-pipeline
- Ask Copilot/CodeRabbit for comprehensive review of src/extractor/pipeline/steps (focus on 05/06/07/10/14 and new 06c)

Copilot/Code Review plan
- After green local run, open a feature branch and push
- Prepare review prompt with context, scenarios, questions, and request unified diffs
