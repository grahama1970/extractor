Fork: grahama1970/extractor
Branch: feat/stage07-orchestrator
Path: git@github.com:grahama1970/extractor.git#feat/stage07-orchestrator
GitHub: https://github.com/grahama1970/extractor

Project Context
- Goal: Higher‑fidelity PDF extraction than PyMuPDF; Stage‑02 must use Marker predictors only (no PyMuPDF fallback). PyMuPDF is allowed only for PDF annotation rendering.
- Recent work:
  - Stage‑07 refactor: deterministic structural pass, multi‑column ordering heuristic, stricter table‑merge guards, schema validation, resume token, performance metrics.
  - Added requirements parity test; docs and automation for Comet → GitHub Copilot requests.
- Current status:
  - Small 2‑page BHT doc passes end‑to‑end.
  - Failure on a larger doc: “Design Documentation for CV32A65X architecture.pdf” at Stage‑02 (watchdog 900s timeout inside font header processor / polygon overlap path).

Live Features / Scenarios
- Deterministic runs for reproducibility (no 07 LLM plugins, temp=0 elsewhere).
- Accurate runs enable LLM in Stage‑03/06/07 with caching and temperature 0.
- Artifacts per doc: annotated overlays; table verification bundles (crop + CSV/HTML with view.html); reflow outputs with hashes and schema checks; run_all_summary.json; resume token.

Paths (relative)
- Stage‑07:
  - src/extractor/pipeline/steps/07_structural_pass.py
  - src/extractor/pipeline/steps/07_orchestrator.py
  - src/extractor/pipeline/run_all.py
  - src/extractor/pipeline/docs/steps/07_performance_and_multicolumn.md
- Stage‑02 hot path (suspected):
  - src/extractor/core/schema/polygon.py
  - src/extractor/core/processors/font_header.py
  - src/extractor/core/converters/pdf.py
  - src/extractor/pipeline/steps/02_marker_extractor.py
- Automation:
  - scripts/comet_copilot_automation.applescript
  - scripts/remote_copilot_trigger.sh
- Tests:
  - tests/pipeline/test_07_requirements_parity.py
- Failing run artifacts (example):
  - data/results/pipeline_batch/design_documentation_for_cv32a65x_architecture/02_marker_extractor/02_error.json
  - data/results/pipeline_batch/design_documentation_for_cv32a65x_architecture/02_marker_extractor/stage_02_marker.log

Clarifying Questions
1) Polygon hot path: can degenerate polygons (empty/NaN/zero area) or extreme coordinates in polygon.py cause pathological costs in overlap/intersection? Recommend safe guards before computing intersection_pct.
2) Font header processor: is it safe to short‑circuit intersection checks using bbox IoU first and skip pairs below a tiny threshold? Any downstream assumptions that require full polygon math for near‑zero overlaps?
3) Watchdog behavior: when approaching the Stage‑02 watchdog (900s), should we soft‑skip only the font header processor and emit a warning artifact, or hard fail? We must not fallback to PyMuPDF.
4) Resume token: any objections to always writing 07_resume_token.json in summary‑only mode so resume gating is consistent?
5) Multi‑column heuristic in 07: notable edge cases where two‑column ordering harms paragraph order; a simple detection we can log?

Requests for Answers + Unified Diffs (apply to fork/branch above)
1) Safe polygon guards
   - File: src/extractor/core/schema/polygon.py
   - Add:
     - Validity checks for polygon points; treat invalid as non‑overlapping (return 0 safely).
     - Fast bbox non‑overlap early exit in intersection_pct.
     - Clamp bbox on construction; guard empty arrays.
   - Provide a complete unified diff.

2) Font header processor guardrails
   - File: src/extractor/core/processors/font_header.py
   - Add:
     - Bbox IoU prefilter before intersection_pct calls; threshold via env.
     - try/except around pair evaluation; count/log skipped_pairs.
     - Configurable thresholds via env with sane defaults.
   - Provide a unified diff.

3) Stage‑02 watchdog soft‑skip
   - File: src/extractor/pipeline/steps/02_marker_extractor.py
   - Around converter.build_document:
     - If elapsed > 60% of watchdog and font header processor is active, raise a sentinel to skip only that processor.
     - Emit 02_warning.json with processor name, counts, thresholds, and continue.
   - Provide a unified diff.

4) Per‑processor timings
   - File: src/extractor/core/converters/pdf.py
   - Wrap each processor(document) with timing; write 02_processor_timings.json in Stage‑02 output dir.
   - Provide a unified diff.

5) Tests for guards
   - File: tests/core/test_polygon_guards.py (new)
   - Cases: empty points; NaN; huge coordinate span; ensure intersection_pct and bbox don’t throw and return safe values.
   - Provide a unified diff.

6) (If needed) 07 summary‑only resume token
   - File: src/extractor/pipeline/steps/07_orchestrator.py
   - Ensure 07_resume_token.json is always written; include artifact sizes.
   - Provide a unified diff if additional changes are required beyond current behavior.

Acceptance
- Re‑run the failing PDF; Stage‑02 completes within watchdog without PyMuPDF fallback.
- 02_processor_timings.json present; 02_error.json absent; if soft‑skip, 02_warning.json present.
- No regressions on the two‑page BHT run.

Thanks—please include answers to the clarifying questions and attach the unified diffs for items 1–5 (and 6 only if needed).
