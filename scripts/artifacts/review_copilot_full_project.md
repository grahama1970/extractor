Fork: grahama1970/extractor
Branch: feat/section-heuristics-and-overlay
Path: git@github.com:grahama1970/extractor.git#feat/section-heuristics-and-overlay
Repo: https://github.com/grahama1970/extractor

# Request: Comprehensive Project Review (Context + Scenarios)

Please perform a holistic review of this project, focusing on pipeline robustness, determinism, and maintainability. Provide answers to questions, identify risks, and propose unified diffs for targeted fixes.

## Project context (high level)
- Purpose: PDF → structured data pipeline with staged processing and optional LLM/VLM assistance.
- Key stages referenced here:
  - 03 Suspicious headers (VLM-assisted, optional offline guard)
  - 04 Section builder (deterministic headers/levels)
  - 05 Table extractor (Camelot, images, metrics)
  - 06 Figure extractor (images + descriptions via VLM; offline mode supported)
  - 07 Reflow (LLM/VLM structured reflow with pass‑through fallback)
  - 10 Exporters/unified document
- Deterministic additions: stable ordering and `deterministic.json` per stage; Stage 07 `--skip-llm` pass‑through.

## Live features / scenarios to consider
- Deterministic run (no LLM):
  - 05 fixed Camelot policy → 06 descriptions skipped → 07 pass‑through → consistent summaries for fast diffs.
- Online run (with LLM/VLM):
  - 06 describes figures via LiteLLM; 07 performs multimodal reflow using section/table/figure/annotation context.
- Resume/partial reruns via `run_all --resume`.

## Review goals
- Determinism and reproducibility safeguards (ordering, seeds, offline flags).
- API/CLI consistency and discoverability.
- Error handling/diagnostics: help operators root-cause quickly.
- Performance and memory: avoid unnecessary copies; predictable concurrency.
- Security/robustness: no secret leakage in outputs; file path handling.

## Code areas to review (relative paths)
- Pipeline stages modified
  - src/extractor/pipeline/steps/05_table_extractor.py
  - src/extractor/pipeline/steps/06_figure_extractor.py
  - src/extractor/pipeline/steps/07_reflow_section.py
- Runners and orchestration
  - src/extractor/pipeline/run_all.py
  - src/extractor/pipeline/structured_pipeline.py
- Utilities that impact determinism/LLM flow (for awareness)
  - src/extractor/pipeline/utils/litellm_call.py
  - src/extractor/pipeline/utils/diagnostics.py
  - src/extractor/pipeline/utils/image_io.py
  - src/extractor/pipeline/utils/ann_index.py

## Specific questions
1) Are the new deterministic summaries (`deterministic.json`) sufficient for diff-based QA? Should we include rounded bbox or IDs only?
2) Is Stage 07 `--skip-llm` pass‑through behavior adequate for downstream stages and exporters? Any schema caveats?
3) Where should we centralize “deterministic mode” env toggles for discoverability (docs/CLI help)?
4) Are there any concurrency or I/O hot spots in 06/07 that warrant batching or backpressure tweaks?

## What to produce
- A prioritized list of issues/opportunities by category (determinism, API, error handling, perf, security).
- Suggested unified diffs with minimal code changes to address top items.
- If sizable refactors are recommended, include an incremental plan.

## Constraints and acceptance
- Maintain backward compatibility of JSON outputs (existing keys preserved).
- Default paths (LLM/VLM on) must continue to work when credentials are configured.
- Deterministic (offline) mode produces identical `deterministic.json` on re-runs.

## Clarifying inputs for your review
- Example run (deterministic):
  - OFFLINE_PDF_PREDICTORS=1 PYTHONHASHSEED=0 \
    python -m extractor.pipeline.run_all run \
      --resume --skip-llm03 --skip-descriptions06 --skip-llm07
- Outputs to sanity-check:
  - data/results/pipeline/05_table_extractor/json_output/{05_tables.json, deterministic.json}
  - data/results/pipeline/06_figure_extractor/json_output/{06_figures.json, deterministic.json}
  - data/results/pipeline/07_reflow_section/json_output/{07_reflowed.json, deterministic.json}

Thank you—propose minimal patches first, with unified diffs.

