12 Insert Annotations

Purpose
- Load Stage 01 annotations into ArangoDB and optionally create edges to `pdf_objects` on the same page (bridging).

Inputs
- Stage 01 annotations: `01_annotation_processor/json_output/01_annotations.json`.

Outputs
- DB inserts into `annotations` and edges in `pdf_relationships`.

Key Behavior
- `--mode insert|bridge|both`:
  - insert: upsert annotations with `source_pdf` into `annotations`.
  - bridge: create edges annotation ↔ pdf_object filtered by `page_num` AND `source_pdf`.
  - both: perform both actions.

CLI (main)
- `run --annotations <01_annotations.json> -o <results_dir> [--mode insert|bridge|both]`

Environment
- Arango: `ARANGO_HOST/PORT/USER/PASSWORD/DATABASE` (use a dedicated test DB during development).
- Collections: `ARANGO_ANNOTATIONS_COLLECTION`, `GRAPH_VERTEX_COLLECTION`, `GRAPH_EDGE_COLLECTION`, `GRAPH_NAME`.

Downstream
- Enables Stage 07 hybrid search augmentation and future graph traversals.

Implementation Notes (tricky parts)
- Modes:
  - insert: Upserts docs only; safe to run immediately after Stage 01. Idempotent via `_key`.
  - bridge: Requires `pdf_objects` from Stage 10; creates edges on same page and filters by `source_pdf` to avoid cross-document links.
  - both: Convenience mode; performs insert then bridge.
- source_pdf handling: Read from Stage 01 JSON and store on each annotation; used later to filter joins and hybrid queries.
- Graph setup: Ensures graph + edge collection exist, recreates with updated vertex sets when needed (tolerant and idempotent).
- Failure tolerance: DB operations are wrapped to avoid hard failures; logs contain import/edge counts.
