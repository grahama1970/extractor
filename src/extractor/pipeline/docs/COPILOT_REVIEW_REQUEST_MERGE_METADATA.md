# Fix Stage 07 table-merge metadata propagation into reflowed/flattened outputs

## Repository and branch

- **Repo:** `experiments/extractor`
- **Branch:** current working tree (uncommitted); please advise whether to base on an existing feature branch or create a new one.
- **Paths of interest:**
  - `src/extractor/pipeline/steps/07_reflow_section.py`
  - `src/extractor/pipeline/utils/unified_conversion.py`
  - `src/extractor/pipeline/steps/10_arangodb_exporter.py`
  - Outputs inspected under `data/results/pipeline_live_chutes_export7`

## Summary of the problem

- Stage 07 detects cross-page table merges (e.g., p3–p4) and writes `merged_tables` summary, but the per-section table entries in `reflowed_sections` lose `merged_table`, `logical_table_key`, and `merged_pages`.
- Because the metadata is missing by the time `build_unified_document_from_reflow` runs, Stage 10 cannot propagate it; `10_flattened_data.json` shows zero merged objects.
- We need merged metadata preserved on every participating table so downstream (annotator/flatten/export/graph) can trace merged logical tables.

## Objectives

1) In Stage 07, reliably tag all parts of split tables with:
   - `merged_table: true`
   - `logical_table_key` (stable hash for the merge group)
   - `merged_pages` (all pages in the merged logical table)
2) Ensure these fields survive into `unified_document.blocks` and therefore appear in `10_flattened_data.json` and Arango export.
3) Keep existing merge detection (consecutive pages) working for p0–p1 and p3–p4 cases in the BHT fixture.

## Constraints

- Do not change table detection heuristics outside of merge metadata tagging.
- Keep runtime reasonable; avoid extra network calls.
- Keep existing logs and outputs otherwise stable.

## Acceptance criteria

- After running the CHUTES pipeline on `data/input/pipeline/BHT_CV32A65X_reqs.pdf`, `07_reflow_section/json_output/07_reflowed.json` contains `merged_table:true`, `logical_table_key`, and `merged_pages` on each table that is part of a merge (p0–p1 and p3–p4 in the fixture).
- `10_flattened_data.json` contains the same merge fields on the corresponding table objects (count > 0).
- Walkthrough/annotator can reference `logical_table_key` if needed (no regression in existing outputs).

## Test plan

1) Run:  
   `source .venv/bin/activate && set -a && source .env && set +a && PYTHONPATH=src EMBEDDINGS_DISABLE=0 python -m extractor.pipeline.run_pipeline --pdf data/input/pipeline/BHT_CV32A65X_reqs.pdf --out data/results/pipeline_merge_fix --extract-requirements --annotate-pdf --generate-walkthrough`
2) Inspect `data/results/pipeline_merge_fix/07_reflow_section/json_output/07_reflowed.json` and confirm merged tables carry the metadata.
3) Inspect `data/results/pipeline_merge_fix/10_arangodb_exporter/json_output/10_flattened_data.json` and confirm merged tables are present with the same metadata.

## Clarifying questions

1) Can we rely on the Stage 05 `normalized_id` as the primary key for tables across stages, or should we derive our own logical key?
2) Is it acceptable to add a small helper to normalize column signatures (columns + ncol + title) to make merge matching more robust?
3) Should walkthrough/annotator display the `logical_table_key`, or is it sufficient to keep it in the JSON only?

