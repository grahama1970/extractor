10 ArangoDB Exporter

Purpose
- Flatten reflowed sections into ordered `pdf_objects` and bulk-import into ArangoDB.

Inputs
- Reflowed sections JSON (Stage 07) and summaries JSON (Stage 09).

Outputs
- `10_arangodb_exporter/json_output/10_export_confirmation.json` (or `10_flattened_data.json` with `--skip-export`).

Key Behavior
- Chooses `source_pdf` from `reflowed_sections[*].source_pdf` (most common), falling back to `source_files.sections`.
- Adds indexes for common queries and order reconstruction.

CLI (main)
- `run --reflowed <07_reflowed.json> --summaries <09_summaries.json> -o <results_dir> [--skip-export]`

Environment
- `ARANGO_HOST/PORT/USER/PASSWORD/DATABASE`.

Implementation Notes (tricky parts)
- source_pdf selection: Chooses the most common `reflowed_sections[*].source_pdf`; falls back to `source_files.sections` if absent.
- Ordering: Adds `object_index_in_doc` and index for fast reconstruction of document order.
- Text content shaping: Generates text for Tables/Figures from metadata (titles/headers/ai_description) when available; plain text for Text blocks.
- Embeddings: Generated lazily if sentence-transformers are available; failure tolerated (logs warning, continues without embeddings).
- Indexes: Creates persistent/fulltext indexes on first run; safe to re-run.
