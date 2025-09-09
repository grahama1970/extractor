# Pipeline CLI Verification

This guide validates that each pipeline CLI step runs end‑to‑end with real network and ArangoDB access. No mocks or fakes are used. It runs on the sample PDF in `data/input/pipeline/` and writes into `data/results/pipeline`.

- Network: Enabled (uses real LLM calls for stages 03 and 09)
- Database: Uses ArangoDB at `ARANGO_HOST/PORT/USERNAME/PASSWORD`
- Sandbox: None (reads system paths, writes under project and `/tmp`)

## Quick Run

```
bash scripts/verify_pipeline_cli.sh
```

The script performs:
- 01→04: `extract-sections` to produce cleaned PDF, blocks, verified blocks, sections
- 05: Extract tables (Camelot)
- 06: Extract figures + descriptions
- 07: Reflow sections (summary-only snapshot to avoid heavy VLM; embeddings are used)
- 08: Extract requirements (prover skipped; still validates extraction path)
- 09: Summarize sections (real LLM calls; tolerant to non‑JSON provider returns)
- 10: Flatten + export to ArangoDB (creates `pdf_objects` with indexes)
- 11: Create knowledge graph edges in ArangoDB
- 12: Insert annotations and bridge to `pdf_objects`
- 14: Generate final JSON + Markdown report

Every step checks for expected output files; steps 10–12 also hit ArangoDB.

## Environment

- Python: venv at `.venv` (Python 3.10 recommended)
- Env vars: load from `.env` (LLM keys + Arango credentials)

Required keys commonly used by the pipeline:
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` (as configured)
- `ARANGO_HOST`, `ARANGO_PORT`, `ARANGO_USERNAME`, `ARANGO_PASSWORD`, `ARANGO_DATABASE`

## Outputs Verified

- `01_annotation_processor/json_output/01_annotations.json`
- `02_marker_extractor/json_output/02_marker_blocks.json`
- `03_suspicious_headers/json_output/03_verified_blocks.json`
- `04_section_builder/json_output/04_sections.json`
- `05_table_extractor/json_output/05_tables.json`
- `06_figure_extractor/json_output/06_figures.json`
- `07_reflow_section/json_output/07_reflowed.json`
- `08_lean4_theorem_prover/json_output/08_theorems.json`
- `09_section_summarizer/json_output/09_summaries.json`
- `10_arangodb_exporter/json_output/10_export_confirmation.json`
- `11_arango_create_graph/json_output/11_graph_confirmation.json`
- `final_report.json`, `final_report.md`

## Notes

- 02 Marker models: A minimal shim is applied to ensure compatibility with installed `transformers` versions (QuantizedCacheConfig symbol). This keeps the pipeline runnable without altering global dependency pins.
- 08 Lean4: `--skip-proving` avoids requiring the Dockerized prover while still exercising extraction paths.
- 09 Summarizer: Providers sometimes return non‑JSON; the step tolerates this and still emits a results JSON.

If you’d like to run 07 with full VLM reflow (no `--summary-only`) or 08 with real proving, remove those flags and ensure the relevant services/containers are available.
