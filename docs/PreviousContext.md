# Previous Context — Pipeline, Smokes, and Next Steps

This document captures the working context so a restarted agent (or teammate) can quickly continue without re‑deriving decisions.

## Pipeline Overview (10,000‑ft)

- 01_annotation_processor → 02_marker_extractor → 03_suspicious_headers → 04_section_builder → 05_table_extractor → 06_figure_extractor → 07_reflow_section → 08–14
- Key pre‑07 artifacts used by Stage 07:
  - Sections (Stage 04): `data/results/pipeline/04_section_builder/json_output/04_sections.json` + visuals under `visual_output/section_{id}.png`
  - Tables (Stage 05): `data/results/pipeline/05_table_extractor/json_output/05_tables.json` with `pandas_df`, `pandas_metrics{columns, shape, data_density}`, and `table_image_path`.
  - Figures (Stage 06): `data/results/pipeline/06_figure_extractor/json_output/06_figures.json` with `image_path`, `ai_description`, `section_id`.

## Stage 07 — Current Strict Behavior (Gemini)

- Prompt and Schema
  - Operates on Section JSON (not free text). Compact context includes section metadata, trimmed text blocks, subset of tables/figures (first N), and explicit image paths.
  - Strict schema (for Gemini) allows `reflowed_json.blocks` items to be:
    - string (legacy texts),
    - figure block object: `{ type: "figure", title?, caption?, image_ref? }`,
    - table block object: `{ type: "table", columns: string[], rows: (string|number|null)[][] }`.
- Deterministic injection (safety nets)
  - Figure block: if figures exist but none returned, Stage 07 inserts one from Stage 06 (`ai_description` as caption, `image_path` as image_ref).
  - Table block: if tables exist but none returned, Stage 07 inserts one from Stage 05 (`columns` + exact `pandas_df` rows).

## Lessons Learned (Gemini + LiteLLM)

- Do not mix `response_format` and `generation_config` for Gemini. Prefer `response_format`.
- Do not set `max_output_tokens` for Gemini when requiring strict JSON — often leads to empty content.
- Use `temperature=0`, and ensure structured flags are not stripped (avoid global toggles; rely on call‑time settings).
- Validate schemas: object properties must be non‑empty to satisfy Google’s response_schema requirements.

## Smokes — What Exists and Status

- Stage 07 strict (passing):
  - `scripts/smokes/pipeline/smoke_stage07_stage_call_text.py` (function‑path, text‑only)
  - `scripts/smokes/pipeline/smoke_stage07_stage_call_image.py` (function‑path, with image)
  - `scripts/smokes/pipeline/smoke_stage07_complex_full.py` (full CLI strict)
- Stage 07 table/figure smokes:
  - `scripts/smokes/pipeline/smoke_stage07_table_block_strict.py` — asserts a strict table block exists and its first row matches Stage 05 (CURRENTLY FAILS; we will fix table-block exactness next).
  - `scripts/smokes/pipeline/smoke_stage07_figure_propagation.py` — asserts figure is surfaced (now PASS after figure block injection/prompt update).
  - `scripts/smokes/pipeline/smoke_stage07_table_integrity.py` — soft check; can SKIP if no structured tables appear.
- Baselines (passing):
  - `scripts/smokes/pipeline/smoke_stage07_any_json.py` (ANY JSON via litellm_call)
  - `scripts/smokes/pipeline/smoke_stage07_gold_preloaded_litellm.py` (strict via litellm_call)
- CI:
  - `.github/workflows/python-pipeline-smokes.yml` runs `make smokes-python`, `make smokes-stage07-strict` and quick pipeline.

## uv Execution

- All Stage 07 smokes and the rest of pipeline smokes have uv headers (script metadata) and are executable.
- Running a smoke directly (env example):
  - `LITELLM_HTTPX=1 LITELLM_DEBUG=1 LITELLM_DROP_PARAMS=0 STAGE07_SCHEMA_MODE=reflow_json ./scripts/smokes/pipeline/smoke_stage07_stage_call_text.py`

## Key Paths / Artifacts

- Section visuals: `data/results/pipeline/04_section_builder/visual_output/section_{id}.png` (prompt shows the path explicitly for human attachment)
- Stage 06 figures: `06_figure_extractor/visual_output/figure_*.png`
- Stage 07 outputs: `data/results/pipeline/07_reflow_section/json_output/07_reflowed.json`
- Web prompt artifacts:
  - `scripts/artifacts/stage07_web_prompt.txt` (copy/paste user prompt with Section/Tables/Figures JSON + Image Path)
  - `scripts/artifacts/stage07_web_messages.json` (API messages with `{{DATA_URL}}` placeholder)

## Recent Fixes Applied

- Stage 04: Roman numeral map corrected (`D=500`); test added `tests/smoke/test_stage04_roman.py`.
- Stage 07: `llm_timeout` default added, passed from CLI. Corrected `clean_json_string` import (pipeline.utils). Removed global `drop_params` toggles.
- Stage 07: Prompt updated with explicit figure guidance; schema extended for figure/table blocks; safety injection for missing blocks.

## How to Run (Strict)

- Makefile targets:
  - `make smokes-stage07-strict` — strict Stage 07 core smokes.
  - `make smokes-stage07-strict-extended` — includes strict table block smoke.
  - `make smokes-python` — full Python smokes suite.
- Required env vars (secrets):
  - `GEMINI_API_KEY` (or `GOOGLE_API_KEY`)
  - Recommended: `LITELLM_HTTPX=1`, `LITELLM_DEBUG=1`, `LITELLM_DROP_PARAMS=0`.

## Remaining Work to Reach “Structured JSON Section Nodes” Fully

1) Exact Table Blocks (highest priority)
- Ensure strict table blocks reproduce Stage 05 `pandas_df` cell content exactly (no whitespace normalization, no edits). For the BHT PDF, prefer the non‑header table if the first page’s table is header‑only.
- Tighten the strict prompt to explicitly produce a `table` block (columns + rows) when table density is high; otherwise fall back to image reference (`markdown_provenance: image`) as designed.
- Make the strict table smoke a required PASS and remove the soft SKIP path.

2) Figure Blocks Without Injection (medium)
- With the prompt/schema updates, the model should emit figure blocks reliably so we can drop the deterministic injection. Keep injection as a backstop until stable.

3) Consolidate Strict Mode & Reduce Env Toggles (medium)
- Keep `--mode strict` as the default; use minimal only for smoke triage. Confirm all strict smokes run without fallback or injection.

4) Logging & Diagnostics (ongoing)
- Maintain sanitized request payload/response logging for every Stage 07 call to simplify future debugging.

## Quick Start for a Restarted Agent

- Load `.env` (must have `GEMINI_API_KEY`).
- Run strict Stage 07 core smokes: `make smokes-stage07-strict`.
- If all green, run quick pipeline: `make quick-pipeline`.
- To test the web prompt path: `python -m scripts.tools.build_stage07_web_payload` and copy from `scripts/artifacts/stage07_web_prompt.txt`.

## Known Risks / Watchouts

- Gemini strict JSON requires careful parameter discipline (no `generation_config`, no `max_output_tokens`).
- Stage 05 header‑only tables can trip “first row” comparisons. Favor non‑header tables or handle that case in smokes.
- Mixed `blocks` (strings + object blocks) is currently allowed to ease transition; the goal is fully structured blocks.

