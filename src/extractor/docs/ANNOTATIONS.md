# PDF Annotations Guide (Stage 01)

This guide explains exactly how to add PDF annotations so that Stage 01 (`src/extractor/pipeline/steps/01_annotation_processor.py`) can detect them reliably and downstream evals can use them as ground truth.

Goals
- Embed clear, machine-readable expectations in the PDF (near the annotated region) without extra sidecar files.
- Keep authoring simple (works with Acrobat, PDF-XChange, Foxit, Preview where possible).
- Make the Stage 01 pipeline extract everything we need with minimal ambiguity and stable geometry.

What Stage 01 Extracts Today
- Rectangular annotations (e.g., “Square”, “Rectangle”, sometimes tools label as “Box”) are treated as target regions.
- FreeText annotations are collected only for their text content (they are not saved as independent annotations unless `--include-freetext`).
- Stage 01 finds the nearest FreeText (within ~200 pt radius) to a Box and sets it as `human_note` on the Box annotation.
- Stage 01 expands the Box to include the union with the nearest FreeText rectangle and nearby text blocks. It renders a cropped image of this expanded region.
- Stage 01 computes inside/above/below text context and features (font sizes, bold, alignment, spacing, numbering, simple gridline hints).
- Stage 01 builds an LLM prompt using: (a) the cropped region image (if `--images`), (b) text context, (c) the `human_note`.

Key Code References
- FreeText detection and note extraction: `extract_annotations_data()` around where it builds `freetext_notes`.
- Nearest FreeText union and expansion: `_get_expanded_rect()` and `extract_annotations_data()`.
- Box output schema: see `annots_out.append({ ... })` starting where `"id": f"p{pno}_a{idx}"` is set.
- Context prompt: `build_context()` includes inside/above/below blocks and `human_note`.

Authoring Rules (What to Draw)
1) Draw a rectangle (Box) around the content you want evaluated (table, figure, requirements block, section header, etc.).
2) Add a FreeText annotation near the Box (ideally within ~200 points). Stage 01 will treat the nearest FreeText as the Box’s `human_note`.
3) Keep the FreeText compact but structured, so we can parse a stable id and expected output pointer.

FreeText Content: Mini-Schema (Recommended)
Use YAML or JSON in the FreeText “content” field. YAML is convenient to type in most editors.

Example (YAML):
- For a table region
  ```yaml
  id: table_bht_signals_v1
  type: table
  expected_json: src/extractor/evals/datasets/gold/table_bht_signals_v1.json
  notes: 5 columns; header present; expect ~5 rows
  labels: [table_region, interface]
  ```
- For a figure
  ```yaml
  id: fig_bht_state_diagram_v1
  type: figure
  expected_json: src/extractor/evals/datasets/gold/fig_bht_state_diagram_v1.json
  notes: two-bit saturating counter; inferred title ok
  labels: [figure, diagram]
  ```
- For a requirements block
  ```yaml
  id: req_bht_behavior_v1
  type: requirements
  expected_json: src/extractor/evals/datasets/gold/req_bht_behavior_v1.json
  notes: include: "BHT is never flushed"; normalize typos; short bullets ok
  labels: [requirements]
  ```

Example (JSON):
```json
{"id":"table_bht_signals_v1","type":"table","expected_json":"src/extractor/evals/datasets/gold/table_bht_signals_v1.json","notes":"5 columns; ~5 rows"}
```

Minimal Fallback (if you can’t embed YAML/JSON):
- Two lines with `id=` and `expected_json=` are acceptable. Example:
  ```
  id=table_bht_signals_v1
  expected_json=src/extractor/evals/datasets/gold/table_bht_signals_v1.json
  type=table
  ```

Placement & Geometry Guidance
- Place the FreeText close to the Box (within ~200 pt). Stage 01 merges the Box with the nearest FreeText rectangle.
- Avoid overlapping multiple Boxes/FreeTexts tightly in the same area; nearest FreeText wins.
- If annotating a multi-page table, annotate each page’s continuation explicitly; use unique ids (e.g., `_p1`, `_p2`) if needed.
- If the figure is adjacent to the table, keep distinct Boxes, each with its own FreeText.

Expected Gold JSON (Examples)
- Place gold files under `src/extractor/evals/datasets/gold/` (or a project-agreed directory) so they’re versioned with code.
- Keep schemas compact and focused on what we assert in evals.

Table:
```json
{
  "type": "table",
  "columns": ["Signal", "IO", "Description", "Connection", "Type"],
  "min_rows": 5,
  "sample_cells": [{"row":0, "col":"Signal", "value":"clk_i"}]
}
```

Figure:
```json
{
  "type": "figure",
  "title_contains": ["INFERRED", "BHT"],
  "caption_contains": ["two-bit", "saturating"]
}
```

Requirements:
```json
{
  "type": "requirements",
  "items_must_include": [
    "The BHT is never flushed",
    "two-bit saturating counters"
  ]
}
```

How Stage 01 Uses FreeText Today
- The FreeText content (any string) is captured under `human_note` and echoed into the LLM context.
- The LLM returns `interpretation` JSON (title, summary, labels, inferred_object, etc.).
- Stage 01 computes a `relevant_to` list based on keywords/labels (configurable via `config/relevant_rules.json`).

How Eval Harness Will Use FreeText
- We will parse `human_note` to extract `id`, `type`, and `expected_json` when present.
- The eval harness will map annotation id → gold JSON, and then compare extracted structures against gold.
- Until we wire this, it’s still useful to adopt the FreeText mini-schema so future evals “just work.”

Running Stage 01 Locally
- CLI:
  ```bash
  python src/extractor/pipeline/steps/01_annotation_processor.py run \
    data/input/pipeline/BHT_CV32A65X_marked_with_requirements.pdf \
    -o data/results/pipeline \
    --images --include-freetext --debug
  ```
- Outputs saved under `data/results/pipeline/01_annotation_processor/` with:
  - `json_output/01_annotations.json` — parsed annotations + LLM interpretations
  - `visual_output/annot_p{page}_a{index}.png` — cropped region images

Do / Don’t
- Do: Use a Box for each target region; add one FreeText per Box with the mini-schema.
- Do: Keep ids unique and stable. Use a simple naming scheme: `table_*`, `fig_*`, `req_*`.
- Do: Keep FreeText concise and near the Box; avoid long prose.
- Don’t: Overlap Boxes tightly; this makes nearest FreeText ambiguous.
- Don’t: Depend on exotic annotation subtypes; stick to Box and FreeText.

Versioning & Provenance
- Commit both annotated PDFs and gold JSONs so they travel together.
- Include a short “notes” field in FreeText to clarify intent, but keep evaluable parts in gold JSON.

Troubleshooting
- If FreeText isn’t picked up: ensure `--include-freetext` is not required — Stage 01 reads FreeText for `human_note` even when not included. Place it closer to the Box.
- If images are too small: Stage 01 renders at `render_dpi` (default 150). Increase with `--dpi 200` if needed.
- If LLM calls are slow: reduce `--concurrency`, or run with `--images/--no-images` to compare.

FAQ
- Q: Can I annotate in multiple languages?
  - A: Yes. Keep id/expected_json keys in English; labels/notes can be multilingual.
- Q: Can I reference multiple gold files from one FreeText?
  - A: Prefer one id per Box. If needed, split into separate Boxes.
- Q: What if I only know the expected column count, not names?
  - A: Put that in gold JSON: use a `min_columns` field or leave `columns` empty and assert only shape.

---

By following this guide, you’ll make Stage 01’s outputs deterministic and ready for annotation-driven evals. Once your PDFs are annotated, share them and I’ll wire the eval harness to parse `human_note` for `id` and `expected_json` and enforce accuracy checks against the corresponding gold files.
