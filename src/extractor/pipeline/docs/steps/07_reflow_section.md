07 Reflow Section

Purpose
- Reflow sections into clean Markdown using LLM with multimodal context.
- Attach tables/figures and relevant annotations; optionally augment with ArangoDB hybrid search.

Inputs
- Sections JSON (Stage 04), Tables JSON (Stage 05), Figures JSON (Stage 06), optional Stage 01 Annotations JSON.

Outputs
- `07_reflow_section/json_output/07_reflowed.json`

Key Behavior
- Loads annotations by page; attaches on-page annotations to each section; ranks with local embeddings when available.
- ArangoDB hybrid search: on-page annotations filtered by `page` AND `source_pdf` to avoid cross-document bleed; merges with on-page.
- Propagates `source_pdf` from Stage 01 annotations to each section.
- Tables: Performs header normalization and multi-page consolidation at the reflow layer. Specifically:
  - Normalize header cells (remove embedded newlines `\n` and zero-width chars; trim/condense whitespace).
  - Coalesce repeated header rows that appear mid-body across pages.
  - When Stage 05 yields a header-only table on an earlier page and body rows on a later page, merge into a single logical table for the section.
  - Optional deterministic columns: set `STAGE07_FORCE_TABLE_COLUMNS="Signal,IO,..."` to instruct the reflow prompt to use exact column names.

Implementation Notes (tricky parts)
- Consolidation: Joins sections (S04), tables (S05), figures (S06) by `section_id`. Builds `source_text`/`merged_text` fallbacks.
- Annotation attach: Collects candidates across `page_start..page_end`; optional semantic re-ranking via sentence-transformers.
- Hybrid search: Queries Arango `annotations` by `page` and `source_pdf`, optionally augments via graph neighbors and merges/dedupes.
- Images: Table/figure/section images loaded via path normalization with multiple fallback candidates.
- Debug: `STAGE07_DEBUG` adds telemetry fields like `hybrid_status` to help inspect merge decisions.

Header cleanup rationale
- Stage 05 (Camelot) is intentionally conservative and does not rewrite header text (e.g., embedded newlines) or merge split tables.
- Stage 07 is the correct layer to normalize header text and produce clean, user-facing column names because it has full section context
  (including figures/annotations) and can make coherent, section-level decisions.

CLI (main)
- `run --sections <s04.json> --tables <s05.json> --figures <s06.json> [--annotations <s01.json>] -o <results_dir> [--summary-only --include-images/--no-include-images --allow-fallback --bundle]`

Environment
- VLM model (single source): `LITELLM_VLM_MODEL` (e.g., `openai/gpt-5-mini`).
- Session + cache: `LITELLM_SESSION_ID` (logged + cache namespace), `LITELLM_ATTACH_SESSION` (default true).
- Optional ArangoDB for hybrid search.
Notes
- Full mode includes images; `litellm_call` auto-routes GPT‑5 + images via OpenAI Responses API and normalizes output.

Downstream
- Stage 10 flattens and exports reflowed content to `pdf_objects` in ArangoDB.
