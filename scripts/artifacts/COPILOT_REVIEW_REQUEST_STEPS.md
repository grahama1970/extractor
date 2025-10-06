Fork: grahama1970/extractor
Branch: feat/pdfplumber-numeric-audit
Path: git@github.com:grahama1970/extractor.git#feat/pdfplumber-numeric-audit

Scope: Focused review of src/extractor/pipeline/steps (01..07), plus run_all glue.

Goals
- Validate Stage 01 UX-curated ingestion:
  - Schema normalization (annotations[] | boxes_by_page{}) → canonical Stage‑01.
  - Absolute vs normalized coordinates detection.
  - Optional LLM bypass for curated with no human_note.
  - Deterministic guard: llm_concurrency=1 + temp=0 under PIPELINE_DETERMINISTIC.
- Check Stage 03/06/07 deterministic parity (temp=0, bounded concurrency) and no hidden nondeterminism.
- Confirm Stage 05 doc_id threading and fragmentation alias do not break consumers.

Please deliver
- Findings ordered from blocking → non‑blocking.
- Unified diffs to fix issues (minimal patches preferred).
- Note any brittle assumptions around curated overlay/types.

Key files
- src/extractor/pipeline/steps/01_annotation_processor.py
- src/extractor/pipeline/steps/03_suspicious_headers.py
- src/extractor/pipeline/steps/05_table_extractor.py
- src/extractor/pipeline/steps/06_figure_extractor.py
- src/extractor/pipeline/steps/07_reflow_section.py
- src/extractor/pipeline/run_all.py

Context
- Determinism is a requirement for CI smokes; LLM/VLM are required for correctness gates but should be temp=0 with serialized concurrency when deterministic.

