# PR: Table Fusion + Numeric Audit + Optional pdfplumber

- Fork: grahama1970/extractor
- Branch: feat/pdfplumber-numeric-audit
- Path: git@github.com:grahama1970/extractor.git#feat/pdfplumber-numeric-audit

## Context

This PR adds non-breaking improvements to pipeline robustness and observability:

- Stage 05: Candidate fusion with optional `pdfplumber` sources (flag-gated)
- Stage 04: Heading anomaly analyzer + section confidence composition
- Stage 07: Numeric integrity audit (recall/precision) and a smoke summarizer

## Flags / Env

- `TABLE_PDFPLUMBER_ENABLED=1` (default 0)
- `TABLE_PDFPLUMBER_ONLY_ON_FLAGGED=1` (only when Camelot needed fallback)
- Optional: `TABLE_CALIBRATOR_PATH=/path/to/model.pkl` (structure_prob)

## Touched Files (high level)

- New utils: `table_fusion.py`, `section_heading_analyzer.py`, `confidence.py`, `numeric_auditor.py`
- Stage 05: fuse Camelot candidates; optional pdfplumber candidates
- Stage 04: annotate heading anomalies; add section `metadata.confidence`
- Stage 07: inject numeric audit into `metadata.numeric_audit` and fold into confidence
- Smoke: `scripts/smokes/numeric_recall_summary.py`

## Quick Results (BHT CV32A65X.pdf)

- Tables total: 82 (one fused per page)
- Figures total: 5 (pages 16–18, 32)
- Sections total: 4
- Numeric recall summary file: `data/results/pipeline/07_reflow_section/json_output/numeric_recall_summary.json`

## Reviewer Guidance

- Focus diffs:
  - `src/extractor/pipeline/steps/05_table_extractor.py` (fusion hook + pdfplumber gate)
  - `src/extractor/pipeline/steps/04_section_builder.py` (heading analysis + confidence)
  - `src/extractor/pipeline/steps/07_reflow_section.py` (numeric audit wiring)
  - `src/extractor/pipeline/utils/*` (new modules)

### Questions

1. Should `TABLE_PDFPLUMBER_ONLY_ON_FLAGGED` default remain 1 (conservative) or 0?
2. Any objections to promoting numeric recall into a CI smoke for golden PDFs?
3. Preferred placement for a future table calibrator model (repo vs artifact bucket)?

### Requested Output

Please provide:
- Answers to the above questions
- Suggested changes in unified diff form where appropriate
- Any schema or public API concerns

