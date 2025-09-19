# Legacy Agents and Scripts — Deprecations

This document tracks deprecated agent-oriented entrypoints and helper scripts that have been
replaced by the single, minimal CLI surface.

## Deprecated

- extract-pdf agent (historical orchestration docs under various `docs/*` files)
  - Replacement: `python -m src.cli extract <input> <out_dir> [--mode fast|accurate]`
  - Status: keep historical transcripts/reviews for archival reference; do not use for new work.

- `src/extractor/core/scripts/convert_single.py`
  - Replacement: `python -m src.cli extract <pdf> <out_dir> --mode accurate`
  - Status: legacy entrypoint used by the extract-pdf agent; superseded by the unified CLI.

## Notes

- Operator wrappers (`pipeline-run`, `pipeline-run-all`) remain available for JSON envelopes or stage-level runs,
  but the paved road for day-to-day use is the unified CLI above.
