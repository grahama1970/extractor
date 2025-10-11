Context: Pipeline Hardening (Step 07 focus)
Date: 2025-10-11

Scope
- Harden Stage 07 (reflow) JSON discipline and determinism without removing LLM usage.
- Keep low-confidence table image assists (Stage 05→07) and vision preflight.
- Maintain strict JSON on first/compact passes; allow repair only as a gated fallback.

Key Changes
- Added strict JSON utilities
  - `src/extractor/pipeline/utils/json_utils.py`:
    - `STRICT_JSON_GUARD`: single-sourced guard text for prompts.
    - `parse_json_strict(text)`: requires a single JSON object/array; forbids NaN/Infinity; no repair.

- Stage 07 tightening
  - `src/extractor/pipeline/steps/07_reflow_section.py`:
    - Uses `STRICT_JSON_GUARD` in system prompt (compact and full).
    - Adds `stop=["```"]` for non‑Gemini providers on strict/compact/relaxed attempts.
    - Parses strict responses via `parse_json_strict` first; if `STAGE07_STRICT_PARSE_ONLY=1`, fail fast; else falls back to `clean_json_string`.

- Tests
  - `tests/pipeline/test_json_strict.py`: unit tests for strict parser and guard text.
  - Updated `tests/conftest.py` to prepend `src/` to `sys.path` so local code is tested.

- Hygiene
  - Expanded `.gitignore` with heavy local outputs: `artifacts/`, `scripts/artifacts/`, `benchmarks/`, `data/`, `memory/`, `screenshots/`, `prototypes/tabbed/screenshots/`, `prototypes/tabbed/pdfs/`, plus caches.

What remains the same
- Stage 07 still supports image attachments for low‑confidence tables and optional figures (env‑gated).
- scillm adapter path remains available via `USE_LLM_ADAPTER=1`.
- No removal of LLM calls: Stage 05 images feed 07 when confidence is low.

How to run quick verification
- Unit test:
  ```bash
  source .venv/bin/activate || true
  pytest -q tests/pipeline/test_json_strict.py
  ```

- Minimal pipeline slice (example):
  ```bash
  PDF="prototypes/tabbed/pdfs/BHT CV32A65X.pdf" \
  OUT="data/results/pipeline_mvp/BHT_CV32A65X" \
  LITELLM_VLM_MODEL="gemini/gemini-2.5-flash" \
  STAGE07_STRICT_PARSE_ONLY=0 \
  python src/extractor/pipeline/steps/01_annotation_processor.py run "$PDF" -o "$OUT" && \
  python src/extractor/pipeline/steps/02_marker_extractor.py run "$OUT/tmp_pdf/$(basename "${PDF%.*}")_clean.pdf" -o "$OUT" --no-spawn && \
  python src/extractor/pipeline/steps/04_section_builder.py run "$OUT/03_suspicious_headers/json_output/03_verified_blocks.json" --pdf-dir "$OUT/tmp_pdf" -o "$OUT" && \
  python src/extractor/pipeline/steps/05_table_extractor.py run "$OUT/04_section_builder/json_output/04_sections.json" --pdf-dir "$OUT/tmp_pdf" -o "$OUT" && \
  python src/extractor/pipeline/steps/06_figure_extractor.py run "$OUT/03_suspicious_headers/json_output/03_verified_blocks.json" --sections "$OUT/04_section_builder/json_output/04_sections.json" --pdf-dir "$OUT/tmp_pdf" -o "$OUT" && \
  python src/extractor/pipeline/steps/07_reflow_section.py run --sections "$OUT/04_section_builder/json_output/04_sections.json" --tables "$OUT/05_table_extractor/json_output/05_tables.json" --figures "$OUT/06_figure_extractor/json_output/06_figures.json" -o "$OUT"
  ```

Notes for Copilot/CodeRabbit
- This branch keeps JSON/prompt hardening small and testable. The next step is to request a review focusing on:
  - Strict JSON discipline in Stage 07, stop tokens, and determinism knobs.
  - Whether `STRICT_JSON_GUARD` should be shared with Stage 03/09 for consistency.
  - Suggestions for trimming the relaxed fallback while keeping reliability.

Env flags of interest
- `STAGE07_VLM_MODEL`: model id (falls back to `LITELLM_VLM_MODEL`).
- `STAGE07_IMAGE_PROMPT_MAX_TOKENS` (default 1792) / `STAGE07_MAX_TOKENS`.
- `STAGE07_STRICT_PARSE_ONLY` (0|1): if 1, forbid repair fallback.
- `STAGE07_INCLUDE_FIGURES` (0|1), `STAGE07_ATTACH_SECTION_IMAGE` (0|1).
- `USE_LLM_ADAPTER` (0|1): route through scillm adapter.

Owner
- Graham; pipeline steps under `src/extractor/pipeline/steps`.
