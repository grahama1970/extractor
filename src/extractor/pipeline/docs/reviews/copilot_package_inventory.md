# Complete Package Inventory for Copilot

**Branch:** `feature/merge-metadata-prop`  
**Latest Commit:** `fb2a220a`  
**Generated:** 2025-12-22

This file provides the complete inventory that GitHub API truncated.

---

## All 7 Utility Packages (3,528 lines total)

### 1. `utils/reflow/` (1,217 lines) — Stage 07

| File             | Lines | Functions                                                                                                                                     |
| ---------------- | ----- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `__init__.py`    | 78    | Re-exports all                                                                                                                                |
| `tables.py`      | 279   | `normalize_table_text`, `sanitize_table_cell`, `df_map`, `compute_table_confidence`, `compute_table_merges`, `build_table_block_from_stage05` |
| `layout.py`      | 152   | `iou_rect`, `horizontal_iou`, `build_figure_block_from_stage06`, `apply_layout_ordering`                                                      |
| `llm_helpers.py` | 122   | `extract_router_content`, `content_to_json_dict`, `direct_scillm_json`, `get_usage_field`                                                     |
| `prompts.py`     | 276   | `build_reflow_prompt`, `build_compact_prompt`, `build_compact_prompt_simple`                                                                  |
| `data_loader.py` | 310   | `merge_text_blocks`, `get_rows_cols`, `compute_metrics_for_df`, `merge_section_tables`, `consolidate_data`                                    |

### 2. `utils/headers/` (380 lines) — Stage 03

| File            | Lines | Functions                                                                |
| --------------- | ----- | ------------------------------------------------------------------------ |
| `__init__.py`   | 37    | Re-exports all                                                           |
| `heuristics.py` | 106   | `_normalize_header_text`, `_font_signature`, `analyze_header_heuristics` |
| `llm.py`        | 200   | `verify_header_with_llm`, `_normalize_model_alias`                       |
| `priors.py`     | 37    | `_retrieve_prior_decisions` (stub)                                       |

### 3. `utils/tables/` (618 lines) — Stage 05

| File            | Lines | Functions                                                                                                                                 |
| --------------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `__init__.py`   | 54    | Re-exports all                                                                                                                            |
| `extraction.py` | 183   | `CAMELOT_STRATEGIES`, `try_camelot_strategy`, `extract_table_image`, `bbox_tuple_for`                                                     |
| `metrics.py`    | 74    | `generate_pandas_metrics`, `score_table`, `iou`, `horizontal_iou`                                                                         |
| `heuristics.py` | 307   | `is_header_row_table`, `stitch_headers`, `detect_table_caption`, `demote_table_headers_to_text`, `demote_sentence_like_single_row_tables` |

### 4. `utils/visuals/` (559 lines) — Stage 09a

| File            | Lines | Functions                                                                                                                                  |
| --------------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `__init__.py`   | 80    | Re-exports all                                                                                                                             |
| `colors.py`     | 128   | `COLORS`, `HUMAN_KIND`, `TAB_COLORS`, `lighten`, `style_for_kind`, `color_for_kind`                                                        |
| `geometry.py`   | 84    | `safe_get_bbox`, `rect_from_pdf_bbox`, `rect_for_kind`, `coerce_page`                                                                      |
| `formatting.py` | 267   | `wrap_label_lines`, `format_label`, `stable_overlay_id`, `headers_preview_from_table`, `rows_preview_from_table`, `table_payload_from_obj` |

### 5. `utils/prover/` (259 lines) — Stage 08

| File           | Lines | Functions                                                                                        |
| -------------- | ----- | ------------------------------------------------------------------------------------------------ |
| `__init__.py`  | 21    | Re-exports all                                                                                   |
| `execution.py` | 238   | `ProofResult`, `get_cli_cmd`, `prove_via_cli`, `prove_batch_via_cli`, `execute_lean_code_docker` |

### 6. `utils/layout/` (289 lines) — Stage 06b

| File          | Lines | Functions                                                                                                      |
| ------------- | ----- | -------------------------------------------------------------------------------------------------------------- |
| `__init__.py` | 43    | Re-exports all                                                                                                 |
| `geometry.py` | 139   | `norm`, `grid_bbox`, `area`, `aspect`, `iou`, `horizontal_iou`, `summ`, `norm_text`, `text_sha1`, `union_bbox` |
| `columns.py`  | 107   | `detect_columns`, `assign_cols_and_span`, `col_id_for`                                                         |

### 7. `utils/sections/` (206 lines) — Stage 04

| File          | Lines | Functions                                                                                                                                                                                                                                           |
| ------------- | ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `__init__.py` | 31    | Re-exports all                                                                                                                                                                                                                                      |
| `parsing.py`  | 175   | `SECTION_NUMBER_PATTERNS`, `roman_to_int`, `analyze_section_numbering`, `derive_section_depth`, `extract_section_title`, `clean_section_title`, `detect_header_level`, `looks_like_header_text`, `normalize_section_number`, `derive_parent_number` |

---

## Commit History (full)

```
fb2a220a docs: update copilot_handoff.md with Phase 2 completion
19e100f1 refactor: add utils/prover/, utils/layout/, utils/sections/ packages
14e1d40b refactor: add utils/tables/ and utils/visuals/ packages
c36c1c9a refactor(03): add utils/headers/ package per Copilot's plan
7818d6ec refactor(07): add imports from utils/reflow package
9b2c0f86 refactor(reflow): complete utils/reflow package per Copilot's plan
1d806d7a docs: update Copilot handoff with reflow package structure
e9a18243 refactor(reflow): add utils/reflow/ package per Copilot's structure
44decf74 docs: add Copilot handoff for LLM telemetry integration
cf054175 feat(telemetry): add LLMCallRecord schema and log_llm_call helper
b254067b feat(schemas): add Pydantic validation for Stage 07/09 LLM outputs
```

---

## Stage Files (current sizes, duplicates NOT yet deleted)

| Stage | File                         | Lines |
| ----- | ---------------------------- | ----- |
| 03    | `03_suspicious_headers.py`   | 1,731 |
| 04    | `04_section_builder.py`      | 1,620 |
| 05    | `05_table_extractor.py`      | 2,448 |
| 06b   | `06b_layout_sketcher.py`     | 1,575 |
| 07    | `07_reflow_section.py`       | 5,412 |
| 08    | `08_lean4_theorem_prover.py` | 1,627 |
| 09    | `09_section_summarizer.py`   | 889   |
| 09a   | `09a_pdf_annotator.py`       | 2,288 |

---

## Phase 3 Tasks for Copilot

### Task A: Wire imports + delete duplicates

For each stage:

1. Add `from extractor.pipeline.utils.{pkg} import ...`
2. Delete the inline duplicate function definitions
3. Run `pytest tests/pipeline/schemas/` after each

### Task B: Stamp `log_llm_call()` at call sites

| Stage | task_kind           | Route           |
| ----- | ------------------- | --------------- |
| 03    | `"verify_header"`   | `"chutes/vlm"`  |
| 06    | `"figure_describe"` | `"chutes/vlm"`  |
| 07    | `"reflow"`          | `"chutes/text"` |
| 08    | `"lean4_formalize"` | `"chutes/text"` |
| 09    | `"summarize"`       | `"chutes/text"` |

### Recommended order

Start with Stage 04 or 06b (less complex), then 05, 08, 03, 09a, and finally 07 (most complex).
