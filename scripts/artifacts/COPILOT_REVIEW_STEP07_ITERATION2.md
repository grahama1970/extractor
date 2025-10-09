## Fork/Branch/Path
Fork: grahama1970/extractor
Branch: feat/step07-micro-pipeline
Path: git@github.com:grahama1970/extractor.git#feat/step07-micro-pipeline

## Copilot Review Request — Stage‑07 Micro‑Pipeline (Iteration 2)

Context
- Implemented amended approach with Stage‑03–aware gating and continuity.
- Added prompt_source_objects in 07a (first accepted 03 header object per section).
- Added tests (label normalization, continuity, polish suppression).
- Added Arango export scaffolding (07f) for sections/blocks/pdf_objects and edges.

Scenarios / Live Features
- Deterministic per‑section `reflowed_json` assembly with cross‑section table continuity.
- Figures carry image_ref; tables preserve cell text; titles/captions refined only when gated.
- Legacy mirror retained at `07_reflow_section/json_output/07_reflowed.json`.

Paths to Review
- Stage 03: `src/extractor/pipeline/steps/03_suspicious_headers.py`
- Stage 04: `src/extractor/pipeline/steps/04_section_builder.py`
- Stage 05: `src/extractor/pipeline/steps/05_table_extractor.py`
- Stage 06: `src/extractor/pipeline/steps/06_figure_extractor.py`
- Stage 07: `src/extractor/pipeline/steps/07a_section_canonicalizer.py`, `07b_paragraph_polish.py`, `07c_table_title_infer.py`, `07d_figure_caption_refine.py`, `07e_assemble_reflow.py`
- Arango: `src/extractor/pipeline/steps/07f_arango_export.py`
- Utils/tests: `src/extractor/pipeline/utils/label_normalization.py`, tests under `tests/pipeline/steps/`

Clarifying Answers (Locked)
1) sections, blocks, references, unresolved_refs
2) Keep legacy 07_reflowed.json: Yes
3) LLM concurrency: 4
4) Hash caching: Yes
5) Preserve reflowed_json: Yes
6) Cross‑section continuity: Yes (in 07a)
7) Offline LLM flag: STAGE07_DISABLE_LLM=1

Requests (Unified Diffs + Minimal Changes)
1) 07a continuity matcher: If you recommend tokenized header‑row matching or 03‑assisted thresholds (distance/overlap), return a minimal patch to `_likely_continuation`.
2) 07b/07c/07d prompts & gates: precise prompt strings/thresholds; supply diffs if you prefer variants.
3) Arango 07f: confirm collections/edges and provide existence checks or glue if desired.
4) Tests: add a real BHT CV32A65X acceptance test or refine the synthetic ones.

Repros
- 07a:
  `python src/extractor/pipeline/steps/07a_section_canonicalizer.py run --sections data/results/pipeline/04_section_builder/json_output/04_sections.json --tables data/results/pipeline/05_table_extractor/json_output/05_tables.json --figures data/results/pipeline/06_figure_extractor/json_output/06_figures.json --verified03 data/results/pipeline/03_suspicious_headers/json_output/03_verified_blocks.json -o data/results/pipeline`
- 07b/07c/07d (respect STAGE07_DISABLE_LLM): run per stage.
- 07e assemble:
  `python src/extractor/pipeline/steps/07e_assemble_reflow.py run --canonical data/results/pipeline/07a_section_canonicalizer/json_output/07a_canonical.json --polish data/results/pipeline/07b_paragraph_polish/07b_paragraph_polish.json --table-titles data/results/pipeline/07c_table_title_infer/07c_table_title_infer.json --figure-captions data/results/pipeline/07d_figure_caption_refine/07d_figure_caption_refine.json -o data/results/pipeline`

Acceptance
- Reflowed JSON present per section; continuity merged as specified; provenance populated; deterministic behavior retained; tests pass.

Thanks — please return answers and unified diffs.

