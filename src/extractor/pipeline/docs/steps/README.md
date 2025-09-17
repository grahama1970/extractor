Steps Documentation

- Naming: one markdown per step matching the script, e.g. `01_annotation_processor.md`.
- Scope: keep each file short and actionable (what it does, inputs/outputs, flags, side effects).
- Update on change: when a step’s behavior or flags change, update its doc in the same PR.

Index
- 01_annotation_processor.md
- 03_suspicious_headers.md
- 07_reflow_section.md
- 10_arangodb_exporter.md
- 12_insert_annotations.md

Happy Path & External Annotations
---------------------------------
- One command (CLI): `pipeline-happy` runs the full pipeline on the canonical BHT sample, validates tolerant golds, and writes a run summary (score) + final report.
- One button (UI): In the Tabbed app, click “Extract” to POST normalized annotations (per‑page boxes) to the pipeline bridge. The bridge stages Stage‑01 JSON and a clean PDF, then runs the pipeline with validation. After the run, click “Load pipeline annotations” to merge auto suggestions into the UI for review.
- To run from external annotations on the CLI, pass `--annotations-json` and (optionally) `--clean-pdf` to `run_all`.
