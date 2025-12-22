# Pipeline Steps Quick Inventory (2025-11-28)

Purpose: fast reference for which stages are **required by default**, which are **opt‑in**, and which have informational status. See `CONTRACT.md` for the full rules.

## Required in the default accurate pipeline
- 01_annotation_processor.py
- 02_marker_extractor.py
- 03_suspicious_headers.py
- 04_section_builder.py
- 04a_layout_audit.py
- 05_table_extractor.py
- 06_figure_extractor.py
- 06b_layout_sketcher.py
- 07_reflow_section.py
- 07_requirements_miner.py
 - 09_section_summarizer.py  (LLM; now required)
 - 09b_audit.py
 - 10_arangodb_exporter.py (flatten + optional DB load)
 - 10b_embeddings.py (embeddings after flatten; opt-in)

## Opt‑in / conditional
- 00_preflight.py (helper)
- 06a_title_caption_enricher.py (LLM enrich)
- 08_lean4_theorem_prover.py (`--prove` or detected requirements)
- 09a_pdf_annotator.py (visual overlays; on for accurate runs)
 - 11_arango_create_graph.py (needs DB/embeddings)
- 12_insert_annotations.py (DB insert)
- 14_report_generator.py (optional; walkthrough.md is primary journal)

## Informational / parity notes
- Parity enforced (~95%) for pdf, html, md, rst, docx, xml, epub.
- PPTX/XLSX parity is **informational only** (counts reported, not enforced).

## Deprecated / keep parked
- 09a_alt_gutter_labels.py
- Anything moved under `deprecated/` (leave stubs if relocated).

Maintenance: update this file when defaults or parity policy change.
