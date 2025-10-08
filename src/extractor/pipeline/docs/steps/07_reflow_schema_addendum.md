# Stage 07 Reflow Schema Addendum

## Section Object (reflowed_sections[*])

Required keys:
- id (string)
- title (string)
- reflowed_text (string)
- section_hash (sha256 of paragraphs + table_ids)
- section_content_hash (alias of section_hash)
- blocks: array[ParagraphBlock]
- tables: array[TableObject]
- figures: array[FigureObject]
- table_merge: { mode, auto_merged[], candidates[], thresholds{hard,soft} }

## ParagraphBlock
{
  "type": "paragraph",
  "text": "<str>",
  "source": {
    "pages": [ <int> ],
    "block_ids": [ "<orig_block_id>", ... ]
  }
}

## TableObject
{
  "table_id": "table/<page>-<page>-<hash8>",
  "table_hash": "<sha256>",
  "row_count": <int>,
  "col_count": <int>,
  "page_span": [ <int> ],
  "pandas_df": [ { "Col1": "val", ... }, ... ],
  "pandas_metrics": { "shape": [rows, cols], "columns": [ ... ], "data_density": <float>? }
}

## Deterministic Hashes

Top-level deterministic_hash = sha256 of each section id + first 128 chars of reflowed_text.
Section section_hash = sha256(paragraph texts + table_ids).
Resume token (07_resume_token.json) captures hash, plugin list, plugin_versions, file sizes.

## Artifacts Overview
| File | Purpose |
|------|---------|
| 07_reflowed.json | Main reflow output |
| 07_reflow_manifest.json | Plugin list, hash, summary_only flag |
| deterministic.json | Hash + plugins + versions |
| 07_resume_token.json | Resume gating (hash, versions, sizes) |
| 07_table_merge_candidates.json | Scored merge candidates |
| 07_table_merge_adjudication.json | LLM / decision results (llm mode) |
| 07_reflow_validate.json | Schema & plugin timing issues |
| 07_reflow_schema_issues.json | Missing required keys (if any) |
