# Extractor Pipeline (Flattened)

This directory contains the simplified post-processing pipeline that turns a PDF into a list of sections. It sits on top of the forked Marker core in `src/extractor/core`.

Key entry points:
- Programmatic: `extractor.pipeline.api.extract_sections(pdf_path, output_dir)`
- CLI: `extract-sections <pdf> [-o OUTPUT_DIR] [--json]`
- Per-step CLIs: scripts in `steps/` each runnable with `python src/extractor/pipeline/steps/<step>.py --help`

Typical flow (01→04):
1. `01_annotation_processor.py` — Clean/prepare PDF (writes `*_clean.pdf`)
2. `02_marker_extractor.py` — Extract blocks using the Marker core
3. `03_suspicious_headers.py` — Verify flagged headers via LLM
4. `04_section_builder.py` — Build validated section hierarchy

Outputs:
- Written to `data/results/pipeline/<stage_name>/json_output/...` by default.
- Gold standards: `data/gold_standards/pipeline/` (validator in `tools/validate_gold_standard.py`).

Examples:
- Programmatic:
  ```python
  from extractor.pipeline.api import extract_sections
  sections, path = extract_sections("data/input/pipeline/BHT_CV32A65X_marked.pdf")
  print(len(sections), path)
  ```
- CLI:
  ```bash
  extract-sections data/input/pipeline/BHT_CV32A65X_marked.pdf -o data/results/pipeline
  ```

Design notes:
- `src/extractor/core` contains the minimally amended Marker fork — fast to update and review.
- Pipeline is intentionally decoupled and step-oriented to aid debugging and reproducibility.
- All large artifacts live under `data/` (not `src/`).
