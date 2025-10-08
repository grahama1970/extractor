# Copilot Code Review Instructions

## Context
- This repository contains an end-to-end PDF extraction pipeline. Our goal is to exceed PyMuPDF heuristics in quality and determinism. Stage‑02 (extraction) MUST use Marker internals (PdfConverter + create_model_dict). PyMuPDF is allowed only for annotations/visualization.

## Review Focus
- Enforce the Extraction Policy: no PyMuPDF/text fallback for Stage‑02 unless explicitly requested by a human.
- Determinism and stability of Stage‑02 outputs (ordering, content hash) and Stage‑05/06 summaries.
- Clear failures vs silent degradation: Stage‑02 should fail fast when predictors are missing.
- Overlay tool safety: clamping rects/labels to page bounds; no crashes on negative/zero rects.

## Key Paths (relative)
- AGENTS.md
- src/extractor/pipeline/steps/02_marker_extractor.py
- src/extractor/pipeline/tools/render_annotated_pdf.py
- scripts/pipeline/run_and_annotate.py

## Constraints & Conventions
- Stage‑02: Marker‑only extraction; fail fast if predictors missing.
- PyMuPDF (`fitz`) only for Stage‑01 annotations and for viewable overlays.
- Keep diffs minimal and focused; preserve Typer CLIs and deterministic ordering.

## What To Deliver
- Concrete answers to questions in `REVIEW_REQUEST.md` with reasoning.
- Suggested unified diffs grouped by concern (enforcement, determinism, error handling, tests).
- Any missed edge cases for overlay clamping and Stage‑02 predictor preflights.

## Repro Commands
```bash
source .venv/bin/activate
uv sync --extra accurate --extra scillm-snapshot

# Single strict run (skip heavy stages)
PYTHONPATH=src OFFLINE_PDF_PREDICTORS=0 \
uv run --active python -m extractor.pipeline.run_all \
  --pdf "data/pdfs/BHT CV32A65X.pdf" \
  --results data/results/strict/BHT --no-resume \
  --summary-only07 --skip-proving08 --skip-export10 --skip-embeddings10 --skip-graph11

# Overlays
uv run --active python -m extractor.pipeline.tools.render_annotated_pdf from-blocks \
  --pdf data/results/strict/BHT/01_annotation_processor/BHT\ CV32A65X_clean.pdf \
  --blocks-json data/results/strict/BHT/02_marker_extractor/json_output/02_marker_blocks.json \
  --out data/results/strict/BHT/annotated/bht__blocks_annotated.pdf
```

