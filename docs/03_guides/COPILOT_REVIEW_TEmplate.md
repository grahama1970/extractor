Fork: grahama1970/extractor
Branch: feat/annotator-pymupdf-restore
Path: git@github.com:grahama1970/extractor.git#feat/annotator-pymupdf-restore

Request: Comprehensive project-wide review with context, scenarios, and actionable diffs

Project overview (context):
- A multi-stage, scriptable PDF extraction pipeline with diagnostics, offline/strict modes, and scenario-driven validation.
- Key areas:
  - Pipeline stages: src/extractor/pipeline/steps/
  - Pipeline orchestration/CLI: src/extractor/pipeline/
  - Utilities: src/extractor/utils/, src/extractor/fast_extract/
  - Scenarios (live features and E2E flows): scenarios/

Live features and scenarios:
- scenarios/run_all.py — scenario orchestrator
- scenarios/pipeline/run_pipeline_all.py — full pipeline runs
- scenarios/pipeline/pdf_e2e_offline.py — offline-mode E2E pipeline smoke
- scenarios/ux/* — UX health checks (CDP/Puppeteer) for prototype routes
- scenarios/extractors/* — format-specific extraction smoke/feature tests

Primary code targets to review:
- Pipeline steps and related orchestration:
  - src/extractor/pipeline/steps/*.py
  - src/extractor/pipeline/pipeline_router.py
  - src/extractor/pipeline/cli_mode.py
  - src/extractor/pipeline/cli_happy.py
  - src/extractor/pipeline/tools/*.py
- Utilities and adapters:
  - src/extractor/utils/report_generator.py
  - src/extractor/fast_extract/pymupdf_fast.py
- Contracts, schemas, and tests:
  - src/contracts.py
  - tests/**/*
- Scenarios (design/coverage/readiness):
  - scenarios/**/*

What we want:
- Architecture-level feedback:
  - Stage boundaries and data contracts (block schema, diagnostics shape, predictor mode flags).
  - Offline/strict mode gates; deterministic behavior and escape hatches.
  - Logging + diagnostics consistency across stages; actionable error taxonomy.
  - Performance hotspots and suggested micro-optimizations with measurable impact.
- Testing and readiness:
  - Scenario coverage — are we missing critical negative cases or large-doc stress tests?
  - Suggestions for additional smokes (fast) and E2E (slower) that improve confidence.
- Developer experience:
  - CLI ergonomics, helpful defaults, and error messages.
  - Repo structure and documentation quick-wins.

Deliverables:
- A prioritized list of issues/opportunities with brief rationale.
- Concrete patch suggestions as unified diffs (small, apply-ready patches).
- If you recommend a migration (e.g., schema cleanup, common diagnostics helper), provide phased diffs.

Clarifying questions you may answer inline:
- Which stage boundaries or interfaces are brittle today?
- Where can we collapse duplicate logic (e.g., env parsing, diagnostics patterns)?
- What minimal tooling (pre-commit, type/lint gates) would yield the best ROI?

Constraints:
- Please do not propose opening a PR; provide diffs we can apply directly.
- Include relative paths to files and, where helpful, line anchors.
- Prefer small, incremental patches with clear commit messages.