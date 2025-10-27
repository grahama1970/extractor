# 06b → 07 Layout Contract

Purpose: describe the deterministic layout sketch produced by Stage 06b
(`06b_layout_sketcher`) and how Stage 07 (`07_reflow_section`) consumes it to
reduce token usage and guide reflow reliably.

Status: stable (schema_version 0.2.0). Additive; safe for older consumers.

## Producer: 06b Layout Sketcher

- Output path: `06b_layout_sketcher/json_output/06b_layout_sketch.json`
- Shape: `{ "sections": { <section_id>: <sketch> } }`

### Sketch schema (v0.2.0)

- `schema_version: "0.2.0"`
- `grid: int` — default `12` (rows = cols).
- `grid_contract: { cell: "half-open", rounding: "floor/ceil", eps: float }`
  - Mapping uses half-open intervals: `[x0, x1)`, `[y0, y1)`.
  - Starts are `floor`, ends are `ceil`, clamped to `[0, grid]` and non-degenerate.
- `columns: [{ id: int, x0: int, x1: int }]`
  - Grid-column bands for the section (derived from the first page with content).
- `elements: [ ... ]`
  - Per-element keys (subset; all deterministic):
    - `kind: "text" | "table" | "figure"`
    - `id: string`
    - `grid_bbox: { x0:int, y0:int, x1:int, y1:int }` (page → grid mapping)
    - `page: int` — page index of the element
    - `column_id: int` — primary column band id
    - `col_ids: int[]` — all column bands with ≥50% horizontal overlap
    - `spans_columns: bool` — true if overlaps ≥2 columns
    - `header_footer_candidate: bool` — near top/bottom bands
    - `reading_order: int` — stable sort: (column → top → left → -area → id)
    - `summary: string` — text snippet (text) or header text (table) or caption (figure)
    - `confidence: float` — tables only; density/metrics proxy when available
    - `llm_assist: bool` — upstream assistance hint if present
    - For floats (`table`/`figure`): optional `anchor_element_id`, `anchor_distance`
  - Note: The raw `bbox` is omitted here; see `elements_original_bbox`.
- `elements_original_bbox: [{ id:string, bbox:[x0,y0,x1,y1] }]`
- `page_breaks: int[]` — sorted distinct page indices present in `elements`.
- `quick_summary: string` — compact text summary (top text and/or first table header).
- `conf: { ordering: float }` — confidence in deterministic ordering (0..1).
- `flow_stream: string` — compact DSL of reading order:
  - Example markers: `[SECTION START]`, `[COLUMNS N]`, `[COL 0 START]`,
    `[PARA id=…]`, `[TABLE id=… header="…"]`, `[FIGURE id=… cap="…"]`,
    `[COL 0 END]`, `[SECTION END]`.
- `table_merge_hints?: [{
     group_id: string,
     tables: [string,string],
     reason: string[],
     scores: { h_iou: float, density_compat: float },
     header_body: bool,
     conf: float
  }]`
  - Non-binding: suggests header/body fragments to merge across pages; used by downstream if desired.

### 06b environment knobs

- `STAGE06B_ALLOW_VLM=0|1` — enable VLM path (default off; deterministic by default)
- `STAGE06B_PYMUPDF_FALLBACK=0|1` — fill missing page text boxes via PyMuPDF (optional)
- `STAGE06B_SOURCE_PDF=/abs/path.pdf` — source PDF for fallback when 04 payload lacks one
- `STAGE06B_EMIT_MERGE_HINTS=0|1` — include `table_merge_hints` (default off)
- Tuning via kwargs/env: `min_gap_ratio`, `header_footer_band`, `place_floats`

## Consumer: 07 Reflow Section

- Attach: 07 loads `06b_layout_sketch.json` and, when enabled, attaches a
  `layout_sketch` dict to each section by `id`.
- Prompt injection: build_section_context_text() injects a compact “Layout Prior”
  JSON block into the textual context with:
  - `ordering_conf` — copied from `sketch.conf.ordering`
  - `columns` — grid bands `[{id,x0,x1}]`
  - `dsl` — `flow_stream` snippet (truncated to 1200 chars to protect token budget)
- Per-section image gating:
  - If `ordering_conf >= STAGE07_LAYOUT_CONF_THRESH` and
    `STAGE07_OMIT_IMAGES_IF_CONFIDENT=1`, images are omitted for that section
    (diagnosed as `images_omitted_due_to_layout_conf`).
  - Guards:
    - `STAGE07_USE_LAYOUT_SKETCH=1` (default)
    - `STAGE07_LAYOUT_CONF_THRESH` (default `0.75`)
    - `STAGE07_OMIT_IMAGES_IF_CONFIDENT=1` (default `1`)

### Current default policy

Stage 07 presently enforces text-only calls (selects a text model and sets
`include_images=False`). The image-omission gating above is implemented and will
take effect if/when images are enabled in 07.

## Minimal example (one section)

```json
{
  "schema_version": "0.2.0",
  "grid": 12,
  "grid_contract": {"cell":"half-open","rounding":"floor/ceil","eps":1e-6},
  "columns": [{"id":0,"x0":0,"x1":6},{"id":1,"x0":6,"x1":12}],
  "elements": [
    {
      "kind": "text",
      "id": "/page/3/Text/12",
      "grid_bbox": {"x0":0, "y0":0, "x1":6, "y1":1},
      "page": 3,
      "column_id": 0,
      "col_ids": [0],
      "spans_columns": false,
      "reading_order": 0,
      "summary": "Introduction …"
    }
  ],
  "elements_original_bbox": [{"id":"/page/3/Text/12","bbox":[72,72,300,96]}],
  "page_breaks": [3],
  "quick_summary": "Introduction …",
  "conf": {"ordering": 0.86},
  "flow_stream": "[SECTION START]\n[COLUMNS 2]\n[COL 0 START]\n[PARA id=/page/3/Text/12] Introduction …\n[COL 0 END]\n[SECTION END]"
}
```

## Compatibility

- The fields above are additive. Stage 07 tolerates missing keys and will skip
  optional behavior when a field isn’t present (e.g., `conf`, `flow_stream`).

