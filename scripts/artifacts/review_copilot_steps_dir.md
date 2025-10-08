Fork: grahama1970/extractor
Branch: feat/section-heuristics-and-overlay
Path: git@github.com:grahama1970/extractor.git#feat/section-heuristics-and-overlay
Repo: https://github.com/grahama1970/extractor

# Request: Full Code Review of src/extractor/pipeline/steps (entire directory)

Please review the entire directory recursively:

- Root: src/extractor/pipeline/steps
- Scope: all stage scripts, CLIs, and utilities in this folder
- Goal: surface correctness issues, determinism pitfalls, API/CLI inconsistencies, and maintainability problems. Propose minimal unified diffs for fixes.

## Context
- This folder contains the pipeline stage entry points (e.g., 01… → 11…), plus stage-specific helpers.
- Recent changes added deterministic ordering and small CLI enhancements in stages 05/06/07. Treat the rest of the directory as in-scope for a holistic review (not just the diff).

## What to focus on
- API surfaces: typer options, env var toggles, and help strings are consistent and discoverable.
- Determinism and reproducibility: avoid unordered iteration over dicts/sets, fix random seeds, stable sorting of outputs, consistent bbox rounding.
- Error handling and diagnostics: actionable messages; do not swallow exceptions that impede debugging.
- Performance: avoid unnecessary re-renders/rasterizations; prefer single-pass scans where sensible; concurrency bounded.
- Security: no leakage of secrets or absolute paths in outputs; robust file path handling.
- JSON schemas: outputs stable across runs; no accidental schema drift.

## Deliverables
- A prioritized list of issues by severity/category.
- Clarifying questions where behavior is ambiguous.
- Unified diffs (minimal, atomic patches) to address the top issues; include file paths and context.

## Helpful anchors
- Directory: src/extractor/pipeline/steps
- Recently changed examples:
  - src/extractor/pipeline/steps/05_table_extractor.py
  - src/extractor/pipeline/steps/06_figure_extractor.py
  - src/extractor/pipeline/steps/07_reflow_section.py

Thank you—please keep patches minimal and focused.

