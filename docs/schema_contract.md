# Pipeline schema contract (concise)

Purpose: stabilize cross‑stage payloads and minimize drift.

## Stage 05 (tables)
- tables[]:
  - page_index: int
  - table_index: int
  - bbox: [x0,y0,x1,y1]
  - pandas_df: records[]
  - pandas_metrics: { shape: [rows, cols], columns: [string], data_density: float }
  - camelot_metrics: { accuracy, whitespace, order }
  - section_id: string (recommended)
  - table_image_path: string (relative)
  - quality_fallback: bool
  - strategy: string

## Stage 06 (figures)
- figures[]:
  - figure_id: string
  - page: int
  - bbox: [x0,y0,x1,y1]
  - image_path: string (relative)
  - caption: string|null (use ai_description when caption is missing)
  - section_id: string (recommended)
  - status: "ok"|"estimated"|"error" (optional)

## Stage 06b (layout sketch)
- sections: { [section_id]:  … }
  - grid: int
  - columns: [{ id, x0, x1 }]  # grid bands
  - elements: [{ kind, id, page, grid_bbox, column_id, col_ids, spans_columns, summary, … }]
  - page_breaks: [int]
  - conf: { ordering: float }
  - flow_stream: string (optional)
  - table_merge_hints: [] (optional)

## Stage 07 (reflow_json)
- reflowed_sections[]:
  - section_id: string
  - title: string
  - blocks: [heading|paragraph|list|table|figure]
  - ocr_corrections: {}
  - improvements_made: string
  - summary: string

Notes
- 05/06 use page‑space bboxes; 06b uses grid‑space.
- Preserve cell strings in tables; normalize whitespace only.
- Add `source`/`status` keys when inferring/patching content for provenance.
