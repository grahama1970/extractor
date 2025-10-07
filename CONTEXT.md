# Project Context — Pipeline Status (2025‑10‑07)

This note captures the exact state of the extractor pipeline after today’s work so we can resume smoothly tomorrow.

## Overview
- End‑to‑end pipeline runs clean on `data/pdfs/BHT CV32A65X.pdf` with summary‑only Stage 07, strict predictors, skip export/graph.
- Determinism hardened for tables/figures; Stage 02 strict fallback gated; Runner writes a richer `index.json` with `exit_status` and `git_rev`.
- Stage 03 creates lightweight stats/meta and clamps concurrency in deterministic mode.

## What Changed Today (key files)
- Stage 02 strict gating + env snapshot
  - `src/extractor/pipeline/steps/02_marker_extractor.py`
    - Strict mode requires Marker internals (no fallback).
    - Lenient mode allows PyMuPDF heuristic fallback and tags `origin: "fallback"`.
    - Writes `02_env_snapshot.json` (imports, redacted env, git_rev, CUDA flags).
- Deterministic summaries
  - `src/extractor/pipeline/steps/05_table_extractor.py` → `tables_content_hash` in `deterministic.json`.
  - `src/extractor/pipeline/steps/06_figure_extractor.py` → `figures_content_hash` in `deterministic.json`.
- Suspicious headers (Stage 03)
  - `src/extractor/pipeline/steps/03_suspicious_headers.py` → writes `03_stage_stats.json`, `03_llm_meta.json`; concurrency=1 when `PIPELINE_DETERMINISTIC=1`; guard when no candidates.
- Runner (end‑to‑end)
  - `src/extractor/pipeline/run_all.py` → clean‑PDF stem assertion (warn by default, strict with `RUN_ALL_STRICT_CLEAN=1`), richer `results/index.json` with `pipeline_version`, `git_rev`, `exit_status`, plus per‑stage outputs; `VALIDATE_STAGES` env filter for GS validation.
- Exporter (Stage 10)
  - `src/extractor/pipeline/steps/10_arangodb_exporter.py` → stable `doc_id` from PDF bytes: `<stem>__<sha8>` when file is accessible.
- Dependency fixes (to keep Stage 02 import chain stable)
  - `pyproject.toml` → added base deps: `urlextract>=1.9.0`, `strip_tags>=0.6`.

## How To Reproduce (today’s run)
- Ensure venv and extras:
  ```bash
  uv sync --extra accurate --extra scillm-snapshot
  ```
- End‑to‑end (strict predictors, summary‑only Stage 07, skip export/graph):
  ```bash
  PYTHONPATH=src \
  RUN_ALL_DEBUG=1 \
  OFFLINE_PDF_PREDICTORS=0 \
  uv run python -m extractor.pipeline.run_all \
    --pdf "data/pdfs/BHT CV32A65X.pdf" \
    --results data/results/pipeline \
    --no-resume \
    --summary-only07 \
    --skip-proving08 \
    --skip-export10 \
    --skip-embeddings10 \
    --skip-graph11
  ```
- Quick Stage‑02 strict only:
  ```bash
  CLEAN_PDF="data/results/pipeline/01_annotation_processor/BHT CV32A65X_clean.pdf" \
  && PYTHONPATH=src OFFLINE_PDF_PREDICTORS=0 RUN_ALL_DEBUG=1 \
  uv run python -m extractor.pipeline.steps.02_marker_extractor run \
    "$CLEAN_PDF" --no-spawn --debug -o data/results/pipeline
  ```

## Where To Look (artifacts)
- Index + final report
  - `data/results/pipeline/index.json` (has `exit_status`, `git_rev`, outputs map)
  - `data/results/pipeline/final_report.md`
- Stage 02 (strict)
  - JSON: `data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks.json`
  - Env snapshot: `data/results/pipeline/02_marker_extractor/02_env_snapshot.json`
  - Log: `data/results/pipeline/02_marker_extractor/stage_02_marker.log`
- Stage 03
  - Verified: `data/results/pipeline/03_suspicious_headers/json_output/03_verified_blocks.json`
  - Meta/Stats: `03_llm_meta.json`, `03_stage_stats.json`
- Stage 05/06 deterministic summaries
  - `data/results/pipeline/05_table_extractor/json_output/deterministic.json`
  - `data/results/pipeline/06_figure_extractor/json_output/deterministic.json`
- Stage 10/11 skip status (when skipped)
  - `data/results/pipeline/10_arangodb_exporter/json_output/10_status.json`
  - `data/results/pipeline/11_arango_create_graph/json_output/11_status.json`

## Current Defaults & Knobs
- Determinism
  - `PIPELINE_DETERMINISTIC=1` → clamps Stage‑03 concurrency to 1; deterministic tables/figures summaries.
  - Stage‑06 jitter removed under deterministic; Stage‑05/06 hashes stable.
- Strictness
  - `OFFLINE_PDF_PREDICTORS=0|false` → Stage 02 requires Marker internals (no fallback).
  - `RUN_ALL_STRICT_CLEAN=1` → fail if clean PDF stem doesn’t match input stem.
- Validation (gold standards)
  - `VALIDATE_STAGES="01,02,03,04,05"` to restrict GS checks to core stages in CI/dev.
- Models / base URL precedence (set in env/.env)
  - Use tenant‑valid slugs for `LITELLM_*` models.

## Status: BHT CV32A65X.pdf (today)
- Pipeline completed successfully.
- Stage‑02 `predictors_present` all True; fallback not used.
- Stage‑03 had 0 suspicious candidates (guard path wrote verified JSON).
- `index.json.exit_status = "success"`.

## Open Follow‑Ups (nice‑to‑have)
- Stage 03: enrich `03_llm_meta.json` with per‑alias failure taxonomy if desired.
- Stage 07: push stable `doc_id` earlier in the reflow payload (Stage 10 already derives it from the PDF path/bytes).
- Runner: optional CI guard to fail if deterministic content hashes drift for 05/06.
- Fix unrelated indentation in `src/extractor/pipeline/cli_happy.py` (does not affect pipeline run).

## Quick Troubleshooting
- Stage 02 import errors
  - Ensure single‑shot extras install:
    ```bash
    uv sync --extra accurate --extra scillm-snapshot
    ```
  - Check: `data/results/pipeline/02_marker_extractor/02_env_snapshot.json` → `imports_status` & `predictors_present`.
- Clean PDF mismatch warning
  - Set `RUN_ALL_STRICT_CLEAN=1` to enforce; otherwise Runner will warn but proceed.

---
Last updated: 2025‑10‑07
