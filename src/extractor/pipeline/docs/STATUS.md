# Pipeline Status (poc_simplified)

This note captures current state, defaults, and how to run/verify stages 01–10. It is a durable handoff across restarts.

## Summary

- Robustness refactor applied across stages with minimal complexity (inline image saving, lazy embedders, safer type checks, stable paths, optional spaCy).
- Default LLM providers switched to OpenAI via LiteLLM using `openai/<model>`.
- Local verification run performed for non-networked stages; LLM-heavy stages are wired but require network + API keys.

## Model & Provider Defaults (SciLLM‑first)

- Provider: SciLLM/Chutes direct (no LiteLLM). Set in `.env`:
  - `CHUTES_API_BASE` and `CHUTES_API_KEY` (required for online stages)
- Stage 07 runs text‑only by default and picks a text model via `get_text_model()`.
- Stage 06 (figures) uses `CHUTES_VLM_MODEL` for optional descriptions.

Notes
- Stage 06b emits deterministic layout (`conf.ordering`, `flow_stream`). Stage 07 consumes this and may omit images per section when confident (see `layout_contract.md`).

## Stage Status (01–10)

- 01 Annotation Processor: Verified. Saves annotation images inline; improved prompt; safer FreeText checks; JSON logs truncated. Output: `01_annotation_processor/{json_output,image_output}`.
- 02 Marker Extractor: CLI/test OK. Runtime requires project Marker internals (`extractor.core.converters.pdf`, `extractor.core.models`). Errors now surface clearly if missing.
- 03 Suspicious Headers: Verified. If suspicious headers exist, uses vision LLM (4o); otherwise writes pass-through `03_verified_blocks.json`.
- 04 Section Builder: Verified. spaCy optional; regex fallback if model missing. Saves section visuals and stores path relative to results root.
- 05 Table Extractor: Code compiles. Runtime requires Camelot + Ghostscript. Install: `uv pip install "camelot-py[cv]"` and system `ghostscript`. Produces images + `05_tables.json`.
- 06 Figure Extractor: CLI OK. Extracts figures with padding, stores image paths relative to results root, includes bbox, and associates with sections; LLM description failures are handled.
- 07 Reflow Section: CLI OK. Lazy SentenceTransformer load; multimodal prompts use 4o. Requires network + API key to run.
- 08 Lean4 Prover: CLI OK. Proving gated (skipped by default). Requirement extraction still uses LLM.
- 09 Section Summarizer: CLI OK. Placeholder summaries emitted locally; checkpoint summaries use LLM (optional).
- 10 Arango Exporter: Verified with `--skip-export`; produces `10_flattened_data.json`. Lazy embedder; exports when DB env vars present.

## Required Dependencies

- PyMuPDF (`fitz`) — already used.
- Optional: spaCy + `en_core_web_sm` (Stage 04 falls back if unavailable).
- Stage 05: `camelot-py[cv]` and system Ghostscript (`apt-get install ghostscript`).
- Stages using embeddings: `sentence-transformers` (loaded lazily and tolerated if missing).

## Environment

- `.env` should include at minimum: `OPENAI_API_KEY` and any ArangoDB config if exporting.
- For local runs: `export PYTHONPATH=src` from repository root.

## Quick Run (non-network path)

- 01 – Annotations (works without LLM on a clean PDF):
  python src/extractor/pipeline/poc_simplified/pipeline/01_annotation_processor.py \
    run src/extractor/pipeline/poc_simplified/proof_of_concept/input/clean_BHT_CV32A65X_marked.pdf \
    -o src/extractor/pipeline/poc_simplified/results

- 03 – Suspicious headers:
  python src/extractor/pipeline/poc_simplified/pipeline/03_suspicious_headers.py run \
    src/extractor/pipeline/poc_simplified/results/02_marker_extractor/json_output/02_marker_blocks.json \
    --pdf-dir src/extractor/pipeline/poc_simplified/results/01_annotation_processor \
    -o src/extractor/pipeline/poc_simplified/results

- 04 – Sections (saves section visuals):
  python src/extractor/pipeline/poc_simplified/pipeline/04_section_builder.py run \
    src/extractor/pipeline/poc_simplified/results/03_suspicious_headers/json_output/03_verified_blocks.json \
    --pdf-dir src/extractor/pipeline/poc_simplified/results/01_annotation_processor \
    -o src/extractor/pipeline/poc_simplified/results

- 05 – Tables (requires Camelot + Ghostscript):
  python src/extractor/pipeline/poc_simplified/pipeline/05_table_extractor.py run \
    src/extractor/pipeline/poc_simplified/results/04_section_builder/json_output/04_sections.json \
    --pdf-dir src/extractor/pipeline/poc_simplified/results/01_annotation_processor \
    -o src/extractor/pipeline/poc_simplified/results

- 06 – Figures (works; LLM description is resilient to failure):
  python src/extractor/pipeline/poc_simplified/pipeline/06_figure_extractor.py run \
    src/extractor/pipeline/poc_simplified/results/02_marker_extractor/json_output/02_marker_blocks.json \
    --sections src/extractor/pipeline/poc_simplified/results/04_section_builder/json_output/04_sections.json \
    --pdf-dir src/extractor/pipeline/poc_simplified/results/01_annotation_processor \
    -o src/extractor/pipeline/poc_simplified/results

- 07 – Reflow (requires network + API):
  python src/extractor/pipeline/poc_simplified/pipeline/07_reflow_section.py run \
    --sections  src/extractor/pipeline/poc_simplified/results/04_section_builder/json_output/04_sections.json \
    --tables    src/extractor/pipeline/poc_simplified/results/05_table_extractor/json_output/05_tables.json \
    --figures   src/extractor/pipeline/poc_simplified/results/06_figure_extractor/json_output/06_figures.json \
    --annotations src/extractor/pipeline/poc_simplified/results/01_annotation_processor/json_output/01_annotations.json \
    -o src/extractor/pipeline/poc_simplified/results

- 09 – Summaries (placeholder is local, checkpoint uses LLM):
  python src/extractor/pipeline/poc_simplified/pipeline/09_section_summarizer.py run \
    src/extractor/pipeline/poc_simplified/results/08_lean4_theorem_prover/json_output/08_theorems.json \
    -o src/extractor/pipeline/poc_simplified/results

- 10 – Arango export (skip DB export):
  python src/extractor/pipeline/poc_simplified/pipeline/10_arangodb_exporter.py \
    --reflowed  src/extractor/pipeline/poc_simplified/results/07_reflow_section/json_output/07_reflowed.json \
    --summaries src/extractor/pipeline/poc_simplified/results/09_section_summarizer/json_output/09_summaries.json \
    -o src/extractor/pipeline/poc_simplified/results \
    --skip-export

## Known Gaps / Next Steps

- Stage 05: install `camelot-py[cv]` and Ghostscript; re-run to generate tables and images.
- Stage 06/07/08/09: run with SciLLM credentials (CHUTES_API_*). Stage 07 is text‑only by default.
- Stage 10: after running 07 and 09, rerun without `--skip-export` to load into ArangoDB (ensure DB env vars are set).

## Stage Status (11 & 14)

- 11 Arango Graph: CLI OK. Fixed FAISS doc/embedding alignment (uses `docs_with_embed`). Requires `faiss-cpu` and `sentence-transformers` (loaded at import by module). Can generate edges JSON with `--skip-graph-creation` or write to ArangoDB when DB env vars are set.
- 14 Report Generator: CLI OK. Uses canonical stage folder names and filenames; aggregates real outputs and writes `final_report.json` and `final_report.md` at results root.

## Additional Dependencies

- Stage 11: `faiss-cpu` (for FAISS indexing) and `sentence-transformers` (already used in 07/10; 11 expects available embeddings in input, but library is still needed).

## Additional Runs (11 & 14)

- 11 – Create graph edges (skip DB write):
  python src/extractor/pipeline/poc_simplified/pipeline/11_arango_create_graph.py \
    src/extractor/pipeline/poc_simplified/results/10_arangodb_exporter/json_output/10_flattened_data.json \
    -o src/extractor/pipeline/poc_simplified/results \
    --skip-graph-creation

  To write edges to ArangoDB instead, ensure DB env vars in `.env` (`ARANGO_HOST`, `ARANGO_PORT`, `ARANGO_USER` or `ARANGO_USERNAME`, `ARANGO_PASS`, `ARANGO_DATABASE`) and omit `--skip-graph-creation`.

- 14 – Generate final report:
  python src/extractor/pipeline/poc_simplified/pipeline/14_report_generator.py \
    run src/extractor/pipeline/poc_simplified/results

## Cross-Stage Integration Notes

- Images & Paths: Stages 04 and 06 save images and store paths relative to the results root, so Stage 07 can resolve and embed them reliably.
- Blocks & BBoxes: Stage 06 returns `bbox`; intersections with sections work for 07/05.
- Memory: Stage 01 writes pixmaps immediately; avoids peak RAM spikes.
- Report: Stage 14 reads actual stage folder names and canonical filenames, avoiding stale artifacts.

## Known Gaps / Next Steps (extended)

- Stage 05: install `camelot-py[cv]` and Ghostscript; re-run to generate tables and images.
- Stages 06/07/08/09: run with OpenAI credentials to regenerate live outputs (vision/text models already default to 4o / 4o-mini).
- Stage 10: after running 07 and 09, rerun without `--skip-export` to load into ArangoDB (ensure DB env vars are set).
- Stage 11: if missing `faiss-cpu`, install it (e.g., `uv pip install faiss-cpu`). Confirm `10_flattened_data.json` contains `embedding` arrays for documents to be indexed.
- Stage 14: confirm canonical outputs exist for each stage (01, 02, 03, 04, 05, 06, 07, 10) to get full report coverage.
