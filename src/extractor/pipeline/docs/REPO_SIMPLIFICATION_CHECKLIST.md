# Repo Simplification & Deprecation Checklist

Goal: Simplify the codebase to focus on the essential runtime paths while keeping all current functionality. Preserve the working extraction core (`src/extractor/core`) and the simplified pipeline that converts a PDF into a JSON list of sections (`src/extractor/pipeline/poc_simplified`). Move deprecated and experimental code into an organized structure under `.archive/` without deleting anything.

Assumptions
- Keep: `src/extractor/core` (modified Marker-PDF extraction) and `src/extractor/pipeline/poc_simplified` (current sectionizing pipeline).
- Audit for deprecation: other pipelines, orchestration layers, unused handlers/processors/sub-agents, legacy docs, and experiments.
- Do not break CLI/server entrypoints; ensure they point only to kept code.

## Phase 0 — Guardrails & Baseline
- [ ] Create branch `refactor/simplify-structure`.
- [ ] Snapshot baseline: `git log -1 > BASELINE_COMMIT.txt`.
- [ ] Verify baseline passes: `pytest -q`.
- [ ] Lint/format/type: `ruff check .`, `black .`, `mypy src`.
- [ ] Identify a representative sample PDF for regression (e.g., `data/input/2505.03335v2.pdf`).
- [ ] Record current pipeline outputs as gold baseline (where available).

## Phase 1 — Inventory & Classification
- [ ] Inventory top-level directories and major modules (tree + owners).
- [ ] Classify each as Keep / Migrate / Archive / Remove (Remove → Archive, not delete).
- [ ] Build import usage map for potentially deprecated areas:
  - [ ] `rg -n "from extractor\.(pipeline|handlers|processors|servers|sub_agents|archive|utils)" src`
  - [ ] `rg -n "import extractor\.(pipeline|handlers|processors|servers|sub_agents|archive|utils)" src`
- [ ] Produce a short “Keep vs Archive” table (commit as `docs/KEEP_ARCHIVE_MATRIX.md`).

## Phase 2 — Target Structure (Proposed)
Target structure after simplification (final names confirmed in Phase 1):
- [ ] `src/extractor/core/` (KEEP): core extraction, models, settings, converters, renderer.
- [ ] `src/extractor/pipeline/poc_simplified/` (KEEP): sectionizing pipeline (consider renaming to `pipeline/sections` later, after freeze).
- [ ] `src/extractor/cli/` (KEEP minimal): ensure commands route only to core + `poc_simplified` pipeline.
- [ ] `src/extractor/utils/` (AUDIT): relocate truly shared utilities; move experimental helpers to archive.
- [ ] `scripts/` (AUDIT): keep dev/test scripts; archive one-offs.
- [ ] `docs/` (AUDIT): keep architecture, API, current pipeline docs; archive stale/duplicated content.

## Phase 3 — Organize `.archive/` (Destination Layout)
Create an organized archive with a manifest for future discovery:
- [ ] Create `.archive/README.md` explaining archive policy and browsing.
- [ ] Create `.archive/deprecated/` with structure:
  - [ ] `code/pipeline_legacy/` (old pipelines, stages, orchestrators)
  - [ ] `code/cli_legacy/` (old CLIs or wrappers not referenced anymore)
  - [ ] `code/experiments/` (spikes, PoCs, notebooks, playgrounds)
  - [ ] `docs/` (deprecated docs moved from `docs/` and `docs/pipeline_docs/`)
  - [ ] `tests/` (tests dedicated only to archived code)
- [ ] Add `.archive/deprecated/MANIFEST.md` listing files moved, source → destination, rationale, last known owner.

## Phase 4 — Candidate Moves (After Audit)
Move the following only after import and usage checks are completed:
- Pipeline (legacy):
  - [ ] `src/extractor/pipeline/stages/` → `.archive/deprecated/code/pipeline_legacy/stages/`
  - [ ] `src/extractor/pipeline/orchestrator.py` → `.archive/deprecated/code/pipeline_legacy/`
  - [ ] `src/extractor/pipeline/jq_pdf_pipeline.py` → `.archive/deprecated/code/pipeline_legacy/`
  - [ ] `src/extractor/pipeline/base.py` (if unused by `poc_simplified`) → `.archive/deprecated/code/pipeline_legacy/`
- Non-essential modules (only if not used by `core` or `poc_simplified`):
  - [ ] `src/extractor/handlers/` → `.archive/deprecated/code/handlers/`
  - [ ] `src/extractor/processors/` → `.archive/deprecated/code/processors/` (partial move if some are shared; keep shared in `utils/`)
  - [ ] `src/extractor/servers/` (if superseded by FastAPI in `core/scripts/server.py`) → `.archive/deprecated/code/servers/`
  - [ ] `src/extractor/sub_agents/` → `.archive/deprecated/code/sub_agents/`
  - [ ] `src/messages/` and `src/tmp/` (if only dev-use) → `.archive/deprecated/code/misc/`
- Scripts & tooling:
  - [ ] One-off scripts in `scripts/` (keep `devloop.sh`, stage smoke, etc.) → `.archive/deprecated/code/scripts/`
- Examples, repos, experiments:
  - [ ] `repos/`, `deprecated/` (within repo), `examples/` (non-essential) → `.archive/deprecated/code/experiments/`

Notes
- Use `rg` to confirm zero references before each move; if referenced by `core` or `poc_simplified`, either keep or refactor into shared `utils/`.
- For any moved module that provided public APIs, create a small stub with `warnings.warn(DeprecationWarning, ...)` that imports from the new location (optional, if needed for backward compat).

## Phase 5 — Documentation Reassessment
- [ ] Audit `docs/pipeline_docs/` for relevance to the current `poc_simplified` pipeline.
- [ ] Audit `docs/` root for outdated guidance; mark candidates for archive.
- [ ] Move deprecated docs → `.archive/deprecated/docs/` with index and pointers to current docs.
- [ ] Update `README.md` to reflect simplified structure and current pipeline ownership.
- [ ] Add/refresh `docs/ARCHITECTURE.md` (focus on `core` + `poc_simplified`).
- [ ] Add `docs/DEPRECATION_GUIDE.md` explaining archive structure and how to find legacy materials.

## Phase 6 — CLI & Entrypoints
- [ ] Review `pyproject.toml [project.scripts]` and remove/redirect entrypoints that hit archived code.
- [ ] Ensure `extractor-cli` routes to the simplified pipeline for PDF→sections JSON.
- [ ] Keep FastAPI server (`extractor_server`) if it fronts `core`; remove/redirect legacy server invocations.
- [ ] Update CLI help texts and usage docs to reflect simplified commands.

## Phase 7 — Tests
- [ ] Identify tests that verify `core` and `poc_simplified` pipeline outputs; keep and strengthen.
- [ ] Update imports/paths impacted by moves.
- [ ] Move/skip tests that cover archived modules → `.archive/deprecated/tests/`.
- [ ] Add smoke test: PDF → sections JSON → non-empty, schema-compliant.
- [ ] Add regression test against a known gold standard (if available) or snapshot tests.

## Phase 8 — Tooling, Linting, Type Checking
- [ ] Run `ruff`, `black`, `mypy` on the simplified tree; fix issues.
- [ ] Ensure `scripts/devloop.sh` remains valid and focused on kept code.
- [ ] Optionally add a pre-commit config with the above tools.

## Phase 9 — Verification & Acceptance
- [ ] Run full tests: `pytest -q`.
- [ ] Run pipeline on sample PDF(s) and verify functional parity (or improvements) vs baseline.
- [ ] Verify CLIs and server still run (help, basic commands, `/docs`).
- [ ] Sanity check: `rg` shows no imports from archived modules in kept code.
- [ ] Update `CHANGELOG.md` with refactor summary and migration notes.

## Rollback & Safety
- [ ] All moves are file-system moves (no deletions); archive is versioned.
- [ ] Keep branch until multiple successful test runs post-merge.
- [ ] Provide a one-liner to restore a moved path if needed.

## Appendix — Useful Commands
- Inventory
  - `rg --files src | wc -l`
  - `tree -L 2 src/extractor | less` (if `tree` is installed)
- Import usage checks
  - `rg -n "from extractor\.(pipeline|handlers|processors|servers|sub_agents)" src`
  - `rg -n "import extractor\.(pipeline|handlers|processors|servers|sub_agents)" src`
- Lint/format/type
  - `ruff check .`; `black src tests`; `mypy src`
- Tests
  - `pytest -q` or targeted: `pytest -q -k "pipeline or core"`

---

Owner: Graham (or delegate)
Reviewers: Core maintainers of `core` and `poc_simplified`
Timeline: Short, iterative PRs (1–3 days), each touching a small, verifiable set of moves.

