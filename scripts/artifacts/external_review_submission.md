<!-- Auto-generated on 2025-09-26 -->
# External Review Prompt (Extractor — Canonical v1)

> Goal: Deliver a blunt, evidence‑backed production‑readiness assessment of the Extractor project and a minimal patch set (unified diffs) with tests and doc updates. Keep changes surgical. Ship safety first.

Reviewer persona & tone
- Principal SRE/DevEx + AppSec; fluent with Python/uv, Typer/FastAPI, Vite/React, ArangoDB, CI.
- Be terse, specific, and fail‑closed. Unverified claims must be marked 🔴 (blocking) or 🟡 (needs proof). No hand‑waving.

Project context (declare at top of your report)
- Project: Extractor — Self‑Correcting Agentic Document Processing System (multi‑stage pipeline + tabbed UX)
- Repo root: /home/graham/workspace/experiments/extractor
- Date: <YYYY‑MM‑DD>
- Doc anchors (this repo):
  - Happy Path & CI: `README.md` (Quick Start, CI quick start), `AGENTS.md` (agent workflow/gates)
  - Pipeline overview: `docs/PIPELINE_RUNBOOK.md`, `docs/SMOKES_GUIDE.md`
  - UX prototype: `prototypes/tabbed/html/README.md`, `prototypes/tabbed/docs/workflow.md`
  - Make targets: `Makefile` (CI, smokes, pipeline runs, bundles)

Inputs you have
- This review bundle (code + docs) assembled via our bundler. Treat docs as claims requiring evidence in code and tests. Mark missing/out‑of‑date artifacts as **P0 doc‑debt** with explicit fixes.

How to build the bundle (reference for you; include paths in the report)
- Pipeline focus (recommended first pass):
  ```bash
  mkdir -p scripts/artifacts && \
  python3 scripts/tools/copy_selected_files.py \
    --root src/extractor/pipeline \
    --output scripts/artifacts/extractor_pipeline_bundle.txt
  ```
- UX (tabbed prototype) focus:
  ```bash
  mkdir -p scripts/artifacts && \
  python3 scripts/tools/copy_selected_files.py \
    --root prototypes/tabbed \
    --output scripts/artifacts/tabbed_bundle.txt
  ```
- Optional combined bundle:
  ```bash
  cat scripts/artifacts/extractor_pipeline_bundle.txt \
      scripts/artifacts/tabbed_bundle.txt \
    > scripts/artifacts/extractor_review_bundle.txt
  ```

Research requirements (competitive landscape)
- Develop the landscape using YOUR tools (don’t rely on our links). Deliver 6–10 entries with dated citations. Lenses:
  - PDF/Document extraction pipelines (Marker/Surya, pdfplumber, Unstructured, DocAI/Document AI)
  - Table extraction/repair (Camelot lattice/stream, Tabula, DeepDeSRT)
  - Agentic pipelines for documents (self‑correcting/multi‑stage; quality gates)
  - Graph/knowledge construction from docs (ArangoDB, FAISS, GraphRAG‑style patterns)
- Include a short research log (5–10 bullet queries + links) that we can reproduce.

Focus areas & acceptance criteria (explicit pass/fail)
- Shared (apply to pipeline and UX)
  - Subprocess safety: Prefer argv; avoid `shell=True` in mutating paths (document any necessary allow‑list).
  - Secrets: Never embed secrets in URLs; env/header only; grep/scanner passes.
  - Artifacts: Deterministic outputs under `scripts/artifacts/` or `data/results/...` with timestamps.
  - Observability: Clear logs; failures show actionable messages; resource sampling present when enabled.
- Pipeline specifics (Stages 01–14)
  - Offline policy: Stages 01–09 run offline (no DB writes); DB I/O confined to 10–12. Flag any violations.
  - Import hygiene: No import‑time side effects; CLIs wired through `build_cli()` factories; lazy step imports via `src/extractor/pipeline/steps/__init__.py` remain intact.
  - JSON strictness: LLM stages must either use provider JSON mode or guarded parsing (`clean_json_string`), fail‑closed on invalid JSON; include minimal tests.
  - Concurrency/limits: Respect semaphores, timeouts, and cache in `litellm_call`; no stampedes; bounded memory.
  - Table integrity: Stage 05 cells sanitized minimally; Stage 07 merging honors Stage 05 column order; no invented rows/cols.
  - Reflow prompt: Stage 07’s strict schema rules enforced; figures/tables propagated with references and captions.
  - Flattening & ordering: Stage 10 preserves reading order, emits deterministic `_key` and doc/section IDs.
  - Graph edges: Stage 11 edge schema validation passes; weights in [0,1]; self‑edges only where specified.
  - Degradation: If Arango/FAISS absent, stages 10–12 degrade with clear messages and skip safely.
- UX specifics (Tabbed prototype)
  - Health gate: No Vite overlay; no `console.error`/`pageerror`; `/main` renders with `[data-testid="page-label"]` present.
  - Toolbar/Canvas: Top toolbar does not occlude canvas; pointer draw works (`N` → drag) and chip highlight appears on selection.
  - Thumbnails: Left‑rail and bottom filmstrip modes render; selector presence validated by smokes.
  - Artifacts: Health/log screenshot pairs saved under `scripts/artifacts/` and linked in the report.

Required commands to tie to readiness (run locally; attach key artifact paths)
- Dev CI gate (servers + suite):
  ```bash
  BASE_URL=http://127.0.0.1:8080 \
  BROWSERLESS_DISCOVERY_URL=http://127.0.0.1:9222/json/version \
  make ci
  ```
- Pipeline (offline path):
  ```bash
  make smokes-pipeline-offline
  make run-all-offline
  ```
- Happy path and full runs (as available in your environment):
  ```bash
  make steps-happy
  make quick-pipeline
  # Full requires API keys + Arango
  make pipeline-full
  ```

Output format (strict)
1) Executive verdict (1–2 paragraphs)
   - Readiness: 🔴/🟡/✅
   - Top 5 “will break in prod” with file:line or CLI anchors
2) Competitive landscape matrix (≥6 rows, dated citations)
3) Project assessment by focus area (finding → evidence → minimal patch/diff → tests/smokes → doc diffs)
4) Per‑file code review frame (Critical/Medium/Hygiene/Strengths)
5) Patches grouped into ≤3 minimal PRs (unified diffs only; no refactors)
6) Test plan (deterministic smokes: pipeline + UX)
7) Research log & citations
8) Readiness gate & score (0–100; rubric below)
9) Submission checklist (all must be true):
   - [ ] Offline policy holds (01–09 no DB writes)
   - [ ] Mutating paths avoid `shell=True` (except documented allow‑list)
   - [ ] No secrets in URLs; scanner passes
   - [ ] JSON strictness enforced in LLM stages; invalid JSON fails‑closed
   - [ ] Table merge rules honored; no invented rows/cols
   - [ ] UX health gate passes (overlay/console errors/pageerror = fail)
   - [ ] Patches include smokes/doc diffs; CLIs preserved
   - [ ] Readiness targets produce artifacts matching docs

Readiness scoring rubric (0–100)
- Safety 30, Offline Policy 15, JSON Strictness 10, Concurrency/Perf 10, Artifacts/Repro 10,
  Graph/DB Degradation 10, UX Health 10, Docs/DX 5.

Constraints & non‑negotiables
- Keep changes minimal and surgical; no new runtime deps unless a P0 requires it.
- Preserve existing CLIs (`build_cli()` entry points, Typer apps) unless a P0 forces change; document migrations.
- If evidence is missing, mark 🟡 and state the proof required.

Crucial code to include INLINE in the report (full functions where noted)
- Steps package loader: `src/extractor/pipeline/steps/__init__.py` (lazy alias loader `__getattr__` — FULL)
- Stage 01: `01_annotation_processor.py`
  - `build_cli()` (FULL)
  - `extract_annotations_data(...)` core loop (sufficient excerpt)
  - `SYSTEM_PROMPT` and relevant feature extractors (`_gridline_features`, `_detect_numbering`) (FULL)
- Stage 02: `02_marker_extractor.py` (CLI wiring + extraction harness excerpt)
- Stage 04: `04_section_builder.py`
  - `analyze_section_numbering`, `derive_section_depth`, `build_sections_from_blocks` (FULL)
- Stage 05: `05_table_extractor.py`
  - `generate_pandas_metrics`, `sanitize_cell`, strategy map and I/O wiring (FULL)
- Stage 06: `06_figure_extractor.py`
  - `describe_image_with_llm`, `extract_and_describe_figure` (FULL)
- Stage 07: `07_reflow_section.py`
  - `PROMPT_STRICT_REQUIREMENTS`, `build_reflow_prompt`, `build_section_context_text`, LLM call wrapper (FULL)
- Stage 07½: `07_requirements_miner.py`
  - `_mine_from_paragraph`, `_mine_from_table`, `_summarize` (FULL)
- Stage 08: `08_lean4_theorem_prover.py`
  - `identify_requirements_in_section` and the Lean CLI integration block (excerpt OK)
- Stage 09: `09_section_summarizer.py`
  - `summarize_section` (FULL)
- Stage 10: `10_arangodb_exporter.py`
  - `_derive_doc_set_and_revision`, `_fast_embedding`, `_collect_section_contexts`, flattening emission (excerpt OK)
- Stage 11: `11_arango_create_graph.py`
  - `_validate_edges`, sample relationship builders (FULL)
- Stage 12: `12_insert_annotations.py`
  - `ensure_graph` and insertion loop (excerpt OK)
- Utilities (selected):
  - `utils/litellm_call.py` — `litellm_call(...)` (FULL) and shutdown helper
  - `utils/json_utils.py` — `clean_json_string(...)` (FULL)
  - `utils/diagnostics.py` — resource sampler start/stop + event helpers (excerpt OK)
  - `utils/unified_conversion.py` — entry `build_unified_document_from_reflow` (excerpt OK)

UX acceptance anchors to verify (must attach artifacts)
- From repo root with live servers:
  ```bash
  npm run ux:check           # launches local Chrome
  BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser \
  npm run ux:check:cdp       # CDP attach
  ```
- Required evidence in the report:
  - Screenshot path: `scripts/artifacts/<route>_*.png`
  - Log path: `scripts/artifacts/ux_check_*.log`
  - Summary line items: `toolbarClear=true`, `pointerDrawOk=true`, selector checks

Submission & TTL
- Deliver a SINGLE secret GitHub Gist containing the report (analysis, code excerpts, diffs, test plan, research log).
- Keep it accessible for ≥15 minutes after sending. We will mirror and delete per policy.
- Provide unified diffs ONLY (we apply them); include exact artifact paths you generated.


---
\n## Attachments (local paths)
- scripts/artifacts/extractor_pipeline_bundle.txt
- scripts/artifacts/tabbed_bundle.txt
- scripts/artifacts/extractor_review_bundle.txt
