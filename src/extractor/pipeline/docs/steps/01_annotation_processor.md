01 Annotation Processor

Purpose
- Extract PDF annotations (incl. FreeText), capture local text context and images, compute layout features, run LLM interpretation, emit a cleaned PDF and JSON.
- Assign `relevant_to: ["03","05","07"]` per-annotation using rules in `config/relevant_rules.json`.

Inputs
- PDF with annotations.

Outputs
- `01_annotation_processor/json_output/01_annotations.json`
- `01_annotation_processor/image_output/*.png` (cropped annotation regions)
- `01_annotation_processor/*_clean.pdf`

Key Behavior
- Saves `source_pdf` path in JSON.
- `relevant_to` is a categorical tag for downstream steps (03 headers, 05 tables, 07 reflow) computed via deterministic rules (keywords, inferred object, validator suggestion, features).

Implementation Notes (tricky parts)
- Region expansion (`_get_expanded_rect`):
  - Starts from the annotation rect; optionally unions nearest FreeText rect (within ~200pt) to capture human label context.
  - Adds symmetric vertical expansion with hard “walls” formed by neighboring annotation rects; clamps to page bounds.
  - Optionally expands to full page width when `full_page_width=True`.
- Context blocks selection (`_get_context_blocks`):
  - Splits surrounding text blocks into inside/above/below based on intersection with expanded rect; sorts by proximity.
- Visual/text features:
  - Font size averages, bold detection, alignment estimate (by comparing centers), spacing above/below.
  - Simple numbering detection (e.g., 1.2.3, 1., A., (iv)) for header-like cues.
  - Coarse gridline heuristic with OpenCV morphology to hint table regions.
- Image rendering:
  - Renders clipped region images without drawing annotations (PyMuPDF `annots=False` when available) for clean inputs.

These details remain implemented in code with docstrings; this section summarizes behavior and pitfalls at a glance for maintainers.

CLI (main)
- `run <input_pdf> -o <results_dir> [--model --include-freetext --images --limit --timeout --dpi --cache]`

Environment
- `LITELLM_DEFAULT_MODEL`, image DPI options; no DB required.

Downstream
- Stage 12 (insert) loads this JSON into ArangoDB.
- Stage 03 consumes this JSON via `--annotations` to bias verification.
- Stage 07 optionally uses this JSON; `source_pdf` is propagated for DB hybrid filtering.
