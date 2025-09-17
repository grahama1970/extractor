# Pipeline Status Tracker

Use this to track offline and online validation for each step. Keep notes short and actionable. Check items as they pass.

- Updated: <!-- date will be updated as you run -->

## Legend
- [ ] Not started
- [~] In progress / flaky
- [x] Verified

## Steps

- 01 Annotation Processor
  - Offline: [ ] (N/A – requires LLM)  Notes: Use `--limit` to probe
  - Online:  [ ]  Notes:
  - Artifacts: `01_annotation_processor/json_output/01_annotations.json`, `*_clean.pdf`

- 02 Marker Extractor
  - Offline: [x]  Notes: OK on canonical PDF
  - Online:  [x]  Notes: identical
  - Artifacts: `02_marker_extractor/json_output/02_marker_blocks.json`

- 03 Suspicious Headers
  - Offline: [x]  Notes: No suspicious headers in canonical test
  - Online:  [x]
  - Artifacts: `03_suspicious_headers/json_output/03_verified_blocks.json`

- 04 Section Builder
  - Offline: [x]  Notes: 1 section built in test
  - Online:  [x]
  - Artifacts: `04_section_builder/json_output/04_sections.json`

- 05 Table Extractor
  - Offline: [x]  Notes: Found 2 tables
  - Online:  [x]
  - Artifacts: `05_table_extractor/json_output/05_tables.json`

- 06 Figure Extractor
  - Offline: [x]  Notes: `--skip-descriptions`
  - Online:  [ ]  Notes: Use `LITELLM_VLM_MODEL` (Gemini) for descriptions
  - Artifacts: `06_figure_extractor/json_output/06_figures.json`

- 07 Reflow Section
  - Offline: [x]  Notes: `--summary-only`
  - Online:  [ ]  Notes: Use `--timeout 240`
  - Artifacts: `07_reflow_section/json_output/07_reflowed.json`

- 08 Lean4 Theorem Prover
  - Offline: [x]  Notes: `--skip-proving`
  - Online:  [ ]  Notes: configure `LEAN4_CLI_CMD` for full proving
  - Artifacts: `08_lean4_theorem_prover/json_output/08_theorems.json`

- 09 Section Summarizer
  - Offline: [ ]  Notes: Optional; can skip
  - Online:  [ ]  Notes: `--max-concurrent 8 --timeout 45 --strict-json`
  - Artifacts: `09_section_summarizer/json_output/09_summaries.json`

- 10 Arango Exporter
  - Offline: [x]  Notes: `--skip-export`
  - Online:  [ ]  Notes: `ARANGO_DATABASE=pdf_knowledge_base_test`
  - Artifacts: `10_arangodb_exporter/json_output/10_flattened_data.json` (+ confirmation)

- 11 Arango Create Graph
  - Offline: [x]  Notes: `--skip-graph-creation`
  - Online:  [ ]  Notes: set `GRAPH_ENABLE_RATIONALES=false` initially
  - Artifacts: `11_arango_create_graph/json_output/11_graph_edges.json` (+ confirmation)

- 12 Insert Annotations
  - Offline: [ ]  Notes: Requires DB
  - Online:  [ ]  Notes: Run `--mode both` after 10 if desired
  - Artifacts: `12_insert_annotations/json_output/12_insert_confirmation.json`

- 14 Report Generator
  - Offline: [x]  Notes: Final report generated
  - Online:  [ ]  Notes: Reflects enriched outputs
  - Artifacts: `final_report.json`, `final_report.md`

## Issues / Debug Notes
- Stage 11 CLI fixed: added `rich.progress` imports and corrected main-guard order.
- Stage 09: added `--timeout` to tune LLM latency per request.
- Stage 07: added `--timeout` for per-request LLM calls (recommend 240s).
- Learned: Gemini Flash is lenient on context, but strict JSON + multi-image prompts are more reliable when the JSON instruction appears at the start of the user content and images are attached as input_image parts. We keep litellm_call generic (drop_params on by default) and shape provider-specific prompts in the step.
