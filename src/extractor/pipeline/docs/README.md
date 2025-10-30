# Pipeline Docs (current)

This directory contains current, actionable documentation for the PDF→structured
pipeline. Older planning notes and deprecated materials were moved to `archive/`.

- STATUS.md — canonical run state, env flags, quick commands.
- layout_contract.md — Stage 06b → 07 layout sketch contract and usage.
- steps/ — brief per‑stage notes (kept for active stages).

Archive
- See `archive/` (moved: critiques/, tasks/, guides/, files/, older proposals).

Change log (2025‑10‑27)
- Stage 05: `TABLE_SELECT_ONE_PER_PAGE=false` (keep all tables by default).
- Stage 06b: emits `conf.ordering` and `flow_stream`; consumed by Stage 07.
- Stage 07: runs text‑only by default; can omit images per section when
  layout `ordering_conf` ≥ threshold (see layout_contract.md for flags).
