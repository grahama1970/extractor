Repo: grahama1970/extractor
Branch: feat/remove-step-clis-20251026

Summary
- Added Stage 00 preflight: strips PDF annotations, normalizes rotation, counts image dupes, writes a clean.pdf + manifest (see paths below).
- Stage 03: added parse-error thresholds (warn 5%, fail 20%), DRY_RUN support, and a timings_summary.json writer.
- Stage 05: header-assist token budget default set to 120000; timings/token usage logs improved.
- Stage 07: added DRY_RUN support; write timings_summary.json after attempts; kept Router-only SciLLM calls and compact artifacts.

Artifacts
- Preflight clean PDF: data/results/pipeline/00_preflight/BHT_CV32A65X_with_requirements/clean.pdf
- Preflight manifest: data/results/pipeline/00_preflight/BHT_CV32A65X_with_requirements/manifest.json
- Stage 07 compact prompt: scripts/artifacts/07_section_section_0_prompt_compact.md
- Stage 06b sketch v2 (section_0): scripts/artifacts/06b_section_section_0_sketch_v2.json
- Stage 07 timings (after next run): data/results/pipeline/07_reflow_section/logs/timings.jsonl
- Stage 07 timings summary (after next run): data/results/pipeline/07_reflow_section/logs/timings_summary.json

Exact Inputs for Copilot Review
1) Layout Sketch (06b) — use to assess ops-first and table/figure metadata:
   - scripts/artifacts/06b_section_section_0_sketch_v2.json
2) Stage 07 Compact Prompt — verify schema clarity and determinism:
   - scripts/artifacts/07_section_section_0_prompt_compact.md

Key Non‑SciLLM Questions
1) Layout Sketch
   - Are object IDs unique and stable enough (id/logical_table_id + bbox IoU) to avoid duplication in prompts?
   - Approve rounding bbox to 2 decimals and trimming noisy metrics to save tokens?
2) Ops‑First Rules (07)
   - Stitching: confirm bullet regex and “too_short → list/paragraph” behavior. Any extra list markers to include?
   - Tables: preserve shapes only (rows/cols/header_rows). OK to forbid all cell edits at this stage?
   - Figures: include by default; omit only when ordering_conf ≥ 0.75; include when conf missing. Keep 0.75?
3) Merge Heuristics
   - 06b emits merge_candidates with scores; 07 stitches when total_score ≥ 0.85. Should scoring live solely in 06b, or also validated in 07?
4) Error Policy
   - Stage 03 parse_error: thresholds warn=5%, fail=20%. Do you want different defaults or CI to fail at warn threshold too?
   - Stage 07 schema: keep current strict ‘reflowed_json’ presence enforcement; add stricter block-level validation, or keep tolerant repairs?
5) Observability
   - timings_summary.json fields sufficient (attempts/ok/exceptions/p50/p95)? Add counters for parse_error / budgets_exceeded here too?
6) Profiles & DRY_RUN
   - Simple (no images) vs Strict (images on) env presets acceptable? DRY_RUN=1 keeps logs/artifacts only—OK for CI smoke?

Acceptance Checks Copilot Can Validate
- Stage 07 compact prompt enforces: {reflowed_json, ocr_corrections, improvements_made, summary}; no code fences; block variants limited to paragraph/list/table/figure; deterministic ops-first expectations are explicit.
- 06b sketch contains required fields per object type and is token‑efficient (IDs, bbox, ro, rows/cols, header_rows?).
- Stage 03 thresholds behave: soft-fail for parse_error, hard-fail when ≥ 20%.
- Timings summaries written for 03 and 07.

Notes
- All SciLLM calls remain Router-only; no httpx fallbacks added. This review focuses on non‑SciLLM pipeline robustness, artifact clarity, and determinism.

