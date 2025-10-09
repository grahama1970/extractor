Fork: grahama1970/extractor
Branch: feat/section-heuristics-and-overlay
Path: git@github.com:grahama1970/extractor.git#feat/section-heuristics-and-overlay
Repo: https://github.com/grahama1970/extractor

# Request: Comprehensive Code Review (Scoped to latest changes)

Please review the latest changes in small, verifiable steps. The goal is to ensure deterministic, reproducible outputs for pipeline stages 05–07 without altering intended behavior when LLM/VLM paths are enabled.

## What changed (summary)
- Stage 05 (tables):
  - Enforced deterministic ordering before write (page_index, y0, x0).
  - Wrote a compact `deterministic.json` summary for quick diffs.
- Stage 06 (figures):
  - Enforced deterministic ordering before write (page, y0, x0, figure_id).
  - Wrote a compact `deterministic.json` summary for quick diffs.
- Stage 07 (reflow):
  - Added `--skip-llm` flag (and `STAGE07_SKIP_LLM=1`) to produce a deterministic pass‑through `reflowed_json` without LLM.
  - Wrote `deterministic.json` summarizing section/table/figure anchors.

## Files to review (relative paths)
- src/extractor/pipeline/steps/05_table_extractor.py
- src/extractor/pipeline/steps/06_figure_extractor.py
- src/extractor/pipeline/steps/07_reflow_section.py

## Step-by-step review plan
1) API and CLI surface
   - Confirm new `--skip-llm` option in Stage 07 is documented in the function signature and consistent with env override `STAGE07_SKIP_LLM`.
   - Ensure no breaking change to defaults.
2) Deterministic ordering
   - Verify sorting keys and tie-breakers:
     - 05: (page_index, y0, x0)
     - 06: (page, y0, x0, figure_id)
     - 07 deterministic.json: per-section sorted anchors
   - Confirm stable types (ints/floats/strings) and safe handling of missing bbox.
3) I/O and payloads
   - Ensure `deterministic.json` is written under each stage’s `json_output/` and is logically minimal.
   - Verify existing outputs (05_tables.json, 06_figures.json, 07_reflowed.json) are unchanged in schema/keys.
4) Control flow and error handling
   - In 07 pass‑through path, confirm fallbacks always produce a valid payload and set `reflow_status` appropriately.
   - Confirm no unhandled exceptions in try/except blocks added.
5) Performance and memory
   - Sorting on small lists is O(n log n); acceptable.
   - Ensure no unintended large copies.
6) Style and consistency
   - Confirm names, logging, and minimal changes align with repo conventions.

## What to produce
- A short list of concrete findings ordered by severity.
- Suggested unified diffs for any improvements (minimal patches preferred).
- If you suggest broader refactors, include a separate “later” section.

## Acceptance criteria
- No behavior change in default online (LLM/VLM) path.
- Deterministic re-runs produce identical `deterministic.json` across runs.
- No new lints in touched files (OK if unrelated files fail).

## Clarifying questions (if needed)
- Should Stage 07 pass‑through always emit `reflowed_json` (current) or mirror `SCHEMA_MODE` strictly?
- Any preference for rounding bbox values in the summaries (currently raw/float)?

