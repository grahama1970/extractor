Extractor Pipeline — Status and Plan

Scope: src/extractor/pipeline and subfolders
Last reviewed: 2025-09-09

Summary
- The flattened pipeline (01→14) is implemented with per‑step Typer CLIs under src/extractor/pipeline/steps and an end‑to‑end runner at src/extractor/pipeline/run_all.py.
- Gold standards exist under data/gold_standards/pipeline for each stage. Validation helpers live in src/extractor/pipeline/tools.
- A single-command runner with validation is available: pipeline-run-and-validate and pipeline-quick-smoke. A pure run-all exists: pipeline-run-all run.
- With correct environment (.env, LLM keys, Arango, Lean4 CLI), all stages can run start→finish. Heavy stages have “skip” modes where possible.

How To Run
- Single run-all (full):
  - pipeline-run-all run --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf -o data/results/pipeline
- Single run with stage-by-stage gold checks (recommended):
  - pipeline-run-and-validate --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf --until 14
- Fast smoke (minimizes external deps; still calls LLM for 03/06):
  - pipeline-quick-smoke --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf
- Validate final reflow + theorems against gold:
  - pipeline-validate-gold run --json (uses data/gold_standards/pipeline/gold_standard_output.json)

Environment Prerequisites
- Core: Python 3.10+, virtualenv, pyproject deps installed.
- PDF + Tables: pymupdf (fitz), camelot-py, ghostscript, pandas.
- LLM: litellm configured via .env; set at minimum LITELLM_VLM_MODEL and provider keys. Vision-capable model required for 03/06/07 (e.g., gemini/gemini-2.5-flash or gpt‑5‑vision).
- Lean4 (Stage 08): LEAN4_CLI_CMD (defaults provided in run_all) and the local lean project (optional skip‑proving flag exists).
- ArangoDB (Stages 10–12): ARANGO_HOST/PORT/USER/PASSWORD/DATABASE. sentence-transformers model for embeddings (downloads on first use) and faiss-cpu for Stage 11.

Gold Standards & Validation
- Per‑stage invariants: data/gold_standards/pipeline/*_gs.json. Use:
  - python -m extractor.pipeline.tools.compare_to_gold --output <stage_json> --gold <gs_json>
- End‑to‑end (07/08) parity: pipeline-validate-gold run [--json]
- Stage contract checks: pipeline-validate-gold stage <ID> <path>
- Note: validate_gold_standard.gold subcommand currently points to src/extractor/pipeline/gold_standards (does not exist). See “Gaps” to track fix.

Stage‑by‑Stage Status
- 01_annotation_processor (Green)
  - Input: annotated PDF → Output: 01_annotations.json, *_clean.pdf
  - CLI: run, debug-bundle. Optional LLM usage for interpretations; produces clean PDF deterministically.
  - Gold: 001_annotation_processor_gs.json present.
- 02_marker_extractor (Green)
  - Input: *_clean.pdf → Output: 02_marker_blocks.json (+ suspicious flags)
  - CLI: run, debug-bundle, test. Deterministic; no network.
  - Gold: 002_marker_extractor_gs.json present.
- 03_suspicious_headers (Yellow)
  - Input: 02_marker_blocks.json + PDF → Output: 03_verified_blocks.json (vision LLM)
  - Requires VLM; preflight ensures vision capability. Produces diagnostics and context images.
  - Gold: 003_suspicious_headers_gs.json present.
  - Gap: no offline “skip verification” mode; see “Gaps”.
- 04_section_builder (Green)
  - Input: 03_verified_blocks.json (+ PDF dir) → Output: 04_sections.json
  - CLI: run, robust heuristics and fallbacks.
  - Gold: 004_section_builder_gs.json present.
- 05_table_extractor (Yellow)
  - Input: 04_sections.json + *_clean.pdf → Output: 05_tables.json, images
  - Requires camelot + ghostscript + fitz; multiple strategies; deterministic once deps installed.
  - Gold: 005_table_extractor_gs.json present.
- 06_figure_extractor (Yellow)
  - Input: 02_marker_blocks.json + 04_sections.json + *_clean.pdf → Output: 06_figures.json, images
  - Extracts images; uses VLM for descriptions. Produces results even if descriptions fail (annotates error).
  - Gold: 006_figure_extractor_gs.json present.
  - Gap: no flag to skip LLM descriptions entirely; see “Gaps”.
- 07_reflow_section (Yellow)
  - Input: sections + tables + figures (+ optional annotations) → Output: 07_reflowed.json
  - VLM by default; has --summary-only to avoid LLM and emit merged_text snapshots; supports image attachments + FAISS annotations.
  - Gold: 007_reflow_section_gs.json present.
- 08_lean4_theorem_prover (Yellow)
  - Input: 07_reflowed.json → Output: 08_theorems.json
  - Uses external Lean4 CLI; supports --skip-proving for smoke runs.
  - Gold: 008_lean4_theorem_prover_gs.json present.
- 09_section_summarizer (Yellow)
  - Input: 07_reflowed.json → Output: 09_summaries.json
  - LLM JSON mode with rolling context; strict-json flag; graceful fallback on errors.
  - Gold: 009_section_summarizer_gs.json present.
- 10_arangodb_exporter (Yellow)
  - Input: 07_reflowed + 09_summaries → Output: 10_flattened_data.json and/or 10_export_confirmation.json
  - Requires Arango + embeddings; supports --skip-export while still writing flattened JSON.
  - Gold: 010_arangodb_exporter_gs.json present.
- 11_arango_create_graph (Yellow)
  - Input: 10_flattened_data.json or DB → Output: 11_graph_edges.json or 11_graph_confirmation.json
  - Requires faiss-cpu; supports --skip-graph-creation to emit JSON without DB.
  - Gold: 011_arango_create_graph_gs.json present.
- 12_insert_annotations (Yellow)
  - Input: 01_annotations.json → DB inserts + edges annotation↔pdf_objects
  - Requires Arango. Debug-bundle emits dry-run counts to JSON.
  - Gold: no strict gs required by default (optional checks via compare_to_gold).
- 14_report_generator (Green)
  - Input: results directory → Output: final_report.json / final_report.md + 14_report.json
  - Gold: 014_report_generator_gs.json present.

Current Gaps / Work To Do
1) Add deterministic “no-LLM” toggles for LLM-heavy stages
   - 03_suspicious_headers: add --skip-llm (mark all SectionHeader candidates as “unverified_true” or pass through) to enable offline runs; still emit 03_verified_blocks.json and diagnostics.
   - 06_figure_extractor: add --skip-descriptions to extract images and metadata without VLM calls.
   - 09_section_summarizer: already has strict JSON and graceful fallback; OK.
   - 07_reflow_section: --summary-only implemented; OK.
2) validate_gold_standard.py gold subcommand path
   - Fix _gs_dir() to data/gold_standards/pipeline (current path points to a non‑existent src/extractor/pipeline/gold_standards).
3) Run‑all debug/validation ergonomics
   - Extend pipeline-run-all with flags to propagate common debug controls (e.g., --summary-only, --skip-proving, --skip-export, --skip-graph) and an optional --validate that chains compare_to_gold at each stage.
   - Today, pipeline-run-and-validate covers validation; recommend it for CI and local checks.
4) Embedding model download footprint (Stage 10)
   - Consider env to disable embeddings or use a lighter local model for CI. Option: add --skip-embeddings (store None) while retaining structure.
5) Arango connectivity robustness (Stages 10–12)
   - Improve error messages when ARANGO_PASSWORD missing; add hints for docker-compose setup. Ensure indexes are idempotent (already handled; confirm on fresh DB).
6) Lean4 CLI integration (Stage 08)
   - Document LEAN4_CLI_CMD contract and add a smoke “noop” mode to bypass external dependency while preserving output shape.
7) Gold coverage & drift
   - Gold invariants are structural; add optional “exact content” regression checks for a small, stable test document to catch accidental behavior changes in 02/04/07.

What “Green” End‑to‑End Looks Like
- LLM configured and reachable; Lean4 CLI available (or skip-proving); Arango reachable (or skip DB with flags).
- Commands:
  - Full run with external deps:
    - pipeline-run-all run --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf -o data/results/pipeline --arango-db pdf_knowledge_base_test
    - Then: pipeline-validate-gold run --json
  - CI‑style run with validations and minimal external actions:
    - pipeline-run-and-validate --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf --until 14 (defaults skip-heavy true)
    - For a quick pass including structural outputs of 10/11 without DB:
      - pipeline-quick-smoke --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf

Debugging Aids
- Shared: diagnostics arrays and logs per stage under data/results/pipeline/<stage>/
- Resource sampling: ENABLE_RESOURCE_SAMPLING=1 and SAMPLE_INTERVAL_SEC=2
- Session scoping: LITELLM_SESSION_ID for reproducible caching; LITELLM_ATTACH_SESSION=true
- Stage 03/06/07 write context images to their image_output directories for inspection.

Readiness Assessment
- Steps implemented: 01–07, 08, 09, 10–12, 14 (all present with CLIs and outputs). Most stages have gold invariants.
- Can run each step in isolation via its Typer CLI and compare to a gold invariant file using compare_to_gold.
- End‑to‑end single Typer call exists: pipeline-run-all run; for validations use pipeline-run-and-validate (single call) or pipeline-quick-smoke.
- Blocking factors for strictly offline/CI runs are LLM invocations (03,06,07,09) and external services (08,10–12). Skip/summary modes exist for 07/08/10/11; adding explicit skip flags to 03/06 would complete the offline path.

Next Actions (proposed order)
1) Fix validate_gold_standard gold path (_gs_dir) and add a unit test.
2) Add --skip-llm to 03 and --skip-descriptions to 06; document in README.md.
3) Enhance pipeline-run-all with --validate and pass‑through debug flags; wire to compare_to_gold.
4) Add --skip-embeddings to 10; document a small local SentenceTransformer for CI if embeddings are desired.
5) Provide docker-compose for Arango test DB and .env.example hints for ARANGO_* and LITELLM_*.
6) Optional: add pipeline CI job that runs pipeline-quick-smoke on the sample PDF and uploads final_report.md as artifact.

