# KEEP vs ARCHIVE Matrix (Initial Draft)

Purpose: Guide simplification by classifying modules for retention or archival. “Archive” means move under `.archive/deprecated/` without deletion.

Legend: [K] Keep, [A] Archive (candidate), [R] Refactor/Move, [TBD] Needs inspection

- [K] `src/extractor/core/`
  - Rationale: Core modified Marker-PDF extraction; primary runtime path.
- [R] `src/extractor/pipeline/poc_simplified/` → flatten into `src/extractor/pipeline/`
  - Rationale: Current PDF → sections pipeline; remove nested structure.
- [R/TBD] `src/extractor/cli/`
  - Keep minimal commands; ensure routing to core + simplified pipeline only.
- [TBD] `src/extractor/utils/`
  - Keep shared utilities; split experimental helpers to archive.
- [A] `src/extractor/handlers/`
  - Archive unless actively imported by core/pipeline.
- [A] `src/extractor/processors/`
  - Archive or selectively keep; current refs show legacy processor base.
- [A] `src/extractor/servers/`
  - Prefer `core/scripts/server.py` (FastAPI). Archive legacy servers.
- [A] `src/extractor/sub_agents/`
  - Archive (unused in simplified runtime).
- [A] `src/extractor/prompts/`
  - Likely documentation/generator prompts; archive if not part of runtime.
- [A] `src/extractor/static/`
  - Archived: unused by runtime/tests; moved to `.archive/deprecated/assets/static`.
- [A/TBD] `src/extractor/unified_extractor.py`
  - References `pipeline_config` (missing); mark for archive or rework.
- [K] `src/extractor/core/scripts/server.py`
  - FastAPI server; keep as supported API surface.

Non-code & data
- [K] `tests/`
  - Keep at repo root; prefer not to duplicate under `src/extractor/test`.
- [R] Data assets (gold standards, sample inputs, results)
  - Move under top-level `data/` (see structure proposal). Avoid placing under `src/`.
- [A] Stale docs under `docs/` (status/progress/critiques/code_reviews/tasks/pipeline_docs/06_legacy)
  - Moved to `.archive/deprecated/docs/` with manifest entries.

Next steps
- Run rg usage checks before each move:
  - `rg -n "from extractor\.(pipeline|handlers|processors|servers|sub_agents|prompts|static)" src`
  - `rg -n "import extractor\.(pipeline|handlers|processors|servers|sub_agents|prompts|static)" src`
- Update this matrix with concrete decisions in PRs.

Maintainer sign-off required for any K→A changes.
