# Fork
Fork: grahama1970/extractor
Branch: feat/step07-micro-pipeline
Path: git@github.com:grahama1970/extractor.git#feat/step07-micro-pipeline

## Comprehensive Review Request — Stage‑07 Micro‑Pipeline (07a–07e)

Context (what changed)
- Stage 07 is refactored into deterministic micro‑stages with sparse, gated LLM steps. Enabling diffs were applied to Stages 03–06 to expose IDs/labels/hashes needed for reproducible assembly.
- Determinism, caching, provenance, and clear contracts take priority; LLM is used only where necessary (temp=0).

Live scenarios (must keep working)
- Strict per‑section `reflowed_json` with normalized blocks.
- Continuity merge of multi‑page tables (attach to later section; provenance recorded).
- Figures carry image_ref; table cell text preserved (only whitespace collapse allowed earlier).
- Legacy mirror file remains at `07_reflow_section/json_output/07_reflowed.json`.

What to review (paths)
- Proposal & request: scripts/artifacts/STEP07_REDESIGN_PROPOSAL.md, scripts/artifacts/COMPREHENSIVE_REVIEW_STEP07_MICROPIPELINE.md
- Enabling diffs:
  - src/extractor/pipeline/steps/03_suspicious_headers.py (object_id, normalized_header_text, context_image_path)
  - src/extractor/pipeline/steps/04_section_builder.py (section_content_hash, needs_layout_image)
  - src/extractor/pipeline/steps/05_table_extractor.py (raw_table_id, normalized_label)
  - src/extractor/pipeline/steps/06_figure_extractor.py (normalized_label)
- New Stage‑07 micro‑stages:
  - src/extractor/pipeline/steps/07a_section_canonicalizer.py
  - src/extractor/pipeline/steps/07b_paragraph_polish.py
  - src/extractor/pipeline/steps/07c_table_title_infer.py
  - src/extractor/pipeline/steps/07d_figure_caption_refine.py
  - src/extractor/pipeline/steps/07e_assemble_reflow.py
- Utils & tests:
  - src/extractor/pipeline/utils/label_normalization.py
  - tests/pipeline/steps/test_07a_canonicalizer.py
  - tests/pipeline/steps/test_label_normalization.py

Clarifying answers (locked)
1) collections: sections, blocks, references, unresolved_refs
2) keep legacy 07_reflowed.json: Yes
3) LLM concurrency: 4
4) hash-based caching: Yes
5) preserve reflowed_json top-level: Yes
6) continuity merge across section boundaries: Yes (in 07a)
7) offline mode flag: STAGE07_DISABLE_LLM=1

Blocking questions (seeking your diffs/guidance)
- Image overlays (Stage 03): confirm Section image → Stage 03 overlay → table crops → first figure order; cap via STAGE07_MAX_IMAGES (default 6). If you want 03 overlay used in prompt anywhere else, specify file patterns.
- Continuity heuristic: we implemented same normalized_label or ≥70% header overlap via columns. If you want tokenized header row matching or 03-assisted thresholding baked into 07a, provide the exact matching code.
- Arango export: confirm final collection/edge names for pdf_objects, section_to_pdf_object, block_to_pdf_object and any required fields.

Return (what we want)
- Unified diffs for:
  - Any improvements to 07a continuity matching logic.
  - 07b/07c/07d prompt strings and gating thresholds if you prefer alternatives.
  - Tests for a concrete acceptance case (e.g., BHT CV32A65X: pages 0–1 table merge) and paragraph polish/no‑polish examples.

Repros
- 07a:
  ```
  python src/extractor/pipeline/steps/07a_section_canonicalizer.py run \
    --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
    --tables   data/results/pipeline/05_table_extractor/json_output/05_tables.json \
    --figures  data/results/pipeline/06_figure_extractor/json_output/06_figures.json \
    --verified03 data/results/pipeline/03_suspicious_headers/json_output/03_verified_blocks.json \
    -o data/results/pipeline
  ```
- 07b/07c/07d (gated by STAGE07_DISABLE_LLM): see stage files.
- 07e assemble:
  ```
  python src/extractor/pipeline/steps/07e_assemble_reflow.py run \
    --canonical      data/results/pipeline/07a_section_canonicalizer/json_output/07a_canonical.json \
    --polish         data/results/pipeline/07b_paragraph_polish/07b_paragraph_polish.json \
    --table-titles   data/results/pipeline/07c_table_title_infer/07c_table_title_infer.json \
    --figure-captions data/results/pipeline/07d_figure_caption_refine/07d_figure_caption_refine.json \
    -o data/results/pipeline
  ```

Acceptance
- Reflowed JSON present per section; merged continuity as specified; provenance populated; deterministic behavior retained; tests pass.

Thanks — please return answers and ready-to-apply diffs.

