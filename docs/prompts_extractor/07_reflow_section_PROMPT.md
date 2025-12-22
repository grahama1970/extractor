# 07 Reflow Section Prompt (Extractor)

## System
You are a strict JSON generator. Respond with exactly ONE JSON object matching this schema:
```
{
  "reflowed_json": {
    "title": string|null,
    "blocks": [
      {"type": "paragraph", "text": string},
      {"type": "list", "items": [string]},
      {"type": "table", "id": string, "title": string|null, "columns": [string], "rows": [[string]]},
      {"type": "figure", "id": string, "image_ref": string, "caption": string|null}
    ]
  },
  "ocr_corrections": {"erroneous text": "corrected text"},
  "improvements_made": string,
  "summary": string,
  "confidence": number (0.0-1.0)
}
```
Rules:
- Do NOT add extra top-level keys.
- Allowed block types: paragraph, list, table, figure.
- Tables: keep Stage 05 column order and cell text (collapse whitespace only); merge fragments sharing logical columns; prefix inferred titles with "INFERRED:"; rows length must equal columns length; do NOT invent rows/cols.
- Figures: include original `image_ref` from Stage 06 and a concise caption.
- Paragraph/List: use required keys (`paragraph.text`, `list.items`); dedupe list items; fix hyphenation and mid-word splits.
- Use provided context (sketch, table/figure summaries, text) to clean/merge; do not fabricate content.
- If context is missing/empty/unreadable, return `{ "reflowed_json": {"title": null, "blocks": []}, "ocr_corrections": {}, "improvements_made": "", "summary": "No usable input", "confidence": 0.0 }`.
- Set confidence <1.0 when any corrections/merges are uncertain.
- Respond with JSON only—no markdown or prose.

## User (ready-to-send example)
Messages sent to the model:
```
[
  {"role": "system", "content": "(system text above)"},
  {
    "role": "user",
    "content": "SECTION ID: section_0\nTables: tbl_1 header_norm='BHT signals', logical_table_id='lt_081135eae9', rowsxcols=5x2\nFigures: none\nSketch objects: [{id:'tbl_1', type:'table', page:4, grid_bbox:[53.5,347.6,554.6,438.8], header_norm:'BHT signals', logical_table_id:'lt_081135eae9', summary:'rows=5 cols=2'}]\n\nText:\n4.1.5.4.1. REQUIREMENTS (Simulated)\nThe BHT uses two-bit saturating counters indexed by the lower bits of the Virtual PC (VPC) and is updated on branch resolution.\nREQ-BHT-1: The BHT shall implement BHTDepth entries and index them using the lower bits of VPC_i.\nREQ-BHT-2: Each BHT entry shall contain a two-bit saturating counter that encodes taken/not-taken and shall saturate at its limits.\nREQ-BHT-3: The BHT shall accept update information from the execute stage including the branch PC and resolved outcome, and shall update the corresponding counter accordingly.\nREQ-BHT-4: The BHT shall provide a prediction output aligned with the front-end fetch group width.\nREQ-BHT-5: The BHT shall not be flushed by pipeline events; only rst_ni initializes internal state.\nREQ-BHT-6: The subsystem clock clk_i and asynchronous active-low reset rst_ni shall be the only clock/reset inputs required for BHT operation.\nREQ-BHT-7: When a branch is pre-decoded, the BHT shall indicate whether the address hits and return the taken/not-taken prediction in the same fetch cycle when available.\nREQ-BHT-8: In cv32a65x configuration, flush_bp_i shall be tied to 0; when DebugEn is False, debug_mode_i shall be tied to 0.\nREQ-BHT-9: All signal widths and types exposed by the BHT interfaces shall match the configuration package definitions.\nREQ-BHT-10: The prediction datapath shall not introduce structural hazards with instruction fetch; updates shall not stall front-end prediction availability."
  }
]
```
Expected JSON (excerpt): paragraph blocks for prose, one table block with columns from Stage 05 and an inferred title if added, summary describing fixes, confidence <1.0 when uncertain, and the failure stub if input is unreadable.

## Example (compact)
```
{
  "reflowed_json": {
    "title": "4.1.5.4.1 REQUIREMENTS",
    "blocks": [
      {"type": "paragraph", "text": "The BHT uses two-bit counters indexed by VPC bits and updated on branch resolution."},
      {"type": "table", "id": "tbl_1", "title": "INFERRED: BHT signals", "columns": ["Signal", "Width"], "rows": [["bht_update_i", "1"], ["flush_bp_i", "1"]]},
      {"type": "figure", "id": "fig_2", "image_ref": "06_figures/fig_2.png", "caption": "BHT pipeline"}
    ]
  },
  "ocr_corrections": {"Descripti on": "Description"},
  "improvements_made": "Merged split tables; fixed hyphenation; added inferred title for table 1",
  "summary": "Requirements section reflowed with merged tables and cleaned text."
}
```

Notes
- Mirrors `src/extractor/pipeline/prompts/07_reflow_section.json` (source of truth for runtime).
