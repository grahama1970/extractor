# Extractor Contract Loop Sanity Matrix

This matrix captures the minimum health checks that **must** pass before the
contract loop runs for the extractor pipeline or before an agent edits a given
pipeline stage. Keep this file current; when a new sanity script is created,
update the entry immediately.

## Global Sanity (run before any stage)

| Command | Purpose |
| --- | --- |
| `uv run src/extractor/pipeline/sanity/camelot_sanity.py` | Table extraction baseline (S05 family) |
| `uv run src/extractor/pipeline/sanity/s08_prove_simple_sanity.py` | Validates `scillm.parallel_acompletions_iter` reachability |
| `source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a && python scripts/tools/scillm_quick_doctor.py` | Confirms Chutes env + credentials |
| `python tools/contract_loop/verify_pipeline_contract.py --mode deterministic` | Adapter smoke without debug overrides |
| `python -m tools.contract_loop.run_task_loop --contracts-root contracts/contract_loop` | Runs minimal contract-loop tasks (Codex exec + gates). |

## Step-Specific Coverage

| Step Module | Sanity Command(s) | Coverage Notes |
| --- | --- | --- |
| `s01_annotation_processor.py` | `uv run scripts/smokes/smoke_stage01_artifacts.py` | Ensures annotation JSON + clean PDF artifacts exist. |
| `s02_marker_extractor.py` | `uv run scripts/smokes/smoke_stage02_marker.py` | Verifies minimal block extraction returns data. |
| `s03_suspicious_headers.py` | `uv run scripts/smokes/smoke_stage03_header_text.py` | Confirms header heuristics flag expected text spans. |
| `s04_section_builder.py` | `uv run scripts/smokes/smoke_stage04_sections.py` | Validates hierarchy + bbox stitching for canonical fixture. |
| `s04a_layout_audit.py` | `uv run scripts/smokes/smoke_stage04a_layout_audit.py` | Runs deterministic reading-order audit on synthetic data. |
| `s05_table_extractor.py` | `uv run scripts/smokes/smoke_stage05_tables.py` | Smoke wraps Camelot table extraction on BHT fixture. |
| `s05b_table_describer.py` | `uv run scripts/smokes/smoke_stage05b_table_describer.py` | Copies Stage 05 output into 05b skip-descriptions contract. |
| `s05c_table_merger.py` | `uv run scripts/smokes/smoke_stage05c_table_merger.py` | Confirms continued tables merge into a single record. |
| `s06_figure_extractor.py` | `uv run scripts/smokes/smoke_stage06_figures.py` | Exercises offline figure crop pipeline path. |
| `s06b_figure_describer.py` | `uv run scripts/smokes/smoke_stage06b_figure_describer.py` | Validates skip-descriptions path preserves figure metadata. |
| `s07_duckdb_ingest.py` | `uv run scripts/smokes/smoke_stage07_text.py` | Reflow adapter smoke (LLM JSON) feeding DuckDB ingest. |
| `s08_extract_requirements.py` | `uv run src/extractor/pipeline/sanity/s08_requirements_sanity.py` | Checks `parallel_acompletions_iter` JSON contract for requirements. |
| `s08_lean4_theorem_prover.py` | `uv run scripts/smokes/smoke_stage08_lean4.py` (optional) | Run when Lean4 is enabled; default contract loop skips this step. |
| `s09_section_summarizer.py` | `uv run scripts/smokes/smoke_stage09_summary.py` | Confirms strict JSON summarizer output via adapter. |
| `s10_arangodb_exporter.py` | `uv run scripts/smokes/smoke_stage10_flatten.py` | Ensures flattening logic preserves ordering metadata. |
| `s10_markdown_exporter.py` | `uv run scripts/smokes/smoke_stage10_markdown.py` | Creates synthetic DuckDB + asserts Markdown export contains tables + reqs. |
| `s14_report_generator.py` | `uv run scripts/smokes/smoke_stage14_report.py` | Builds synthetic pipeline tree + validates final report stats. |

> **Rule:** Every row must point to a passing sanity script before contract loop
> work can proceed. Update this file (and the enforcement helper) as each script
> lands so the gate reflects reality.
