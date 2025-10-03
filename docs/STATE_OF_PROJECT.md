# Prompt: Generate/Update This Report Reliably (Happy Path + Critical Lens)

You are an operator agent asked to produce a fresh “State of the Extractor Project” report. Follow these exact steps and write your answer into this file (docs/STATE_OF_PROJECT.md):

1) Validate repo + env
   - Activate venv and env:
     ```bash
     source .venv/bin/activate && \
     set -a && [ -f .env ] && source .env && set +a
     ```
   - Confirm CLI imports resolve:
     ```bash
     PYTHONPATH=$(pwd)/src \
     .venv/bin/python - <<'PY'
     import extractor, sys; print({"ok":True, "py":sys.version.split()[0]})
     PY
     ```

2) Run UX health + core UI smokes
   - Health gate (saves artifacts under scripts/artifacts/):
     ```bash
     BASE_URL=http://127.0.0.1:8080/main \
     node scripts/ux_check_broken.mjs
     ```
   - Core UI smokes (subset is fine for quick status):
     ```bash
     BASE_URL=http://127.0.0.1:8080 \
     node scripts/smokes/ui_keyboard_core.mjs && \
     node scripts/smokes/ui_search_highlight_thumb.mjs
     ```

3) Run API smokes (offline‑friendly)
   ```bash
   BASE_URL=http://127.0.0.1:8000 \
   uv run scripts/smokes/api_oslc_stub.py && \
   uv run scripts/smokes/api_conflicts_save.py
   ```

4) Run pipeline smokes (deterministic)
   ```bash
   PYTHONPATH=$(pwd)/src \
   .venv/bin/python scripts/smokes/pipeline/smoke_reqif_export_v0.py && \
   PYTHONPATH=$(pwd)/src \
   .venv/bin/python scripts/smokes/pipeline/smoke_stage14_rtm_v0.py && \
   PYTHONPATH=$(pwd)/src \
   .venv/bin/python scripts/smokes/pipeline/smoke_resume_manifest.py
   ```

5) Summarize current capabilities (PDF accurate stages 01→14; structured providers; unified CLI; Classic UI collab primitives; Lean4 proving) and map to USER_FLOW.md and docs/03_guides/HAPPYPATH_GUIDE.md.

6) Competitive scan (primary sources; cite URLs inline)
   - PDF annotation UX (search/shortcuts/handles/rails): Adobe Acrobat web, Xodo, PDF.js patterns, Label Studio, PSPDFKit.
   - ReqIF/OSLC interop: ReqIF Studio, OSLC RM 2.1, DOORS Next.

7) Write the report with sections:
   - Executive Summary, Capabilities, Validation Status, Competitive Landscape, Blunt Assessment vs Market, Recommendations/Roadmap (Now/Next/Later), Metrics & SLIs, Risks & Mitigations, References.

8) Keep it operator‑friendly
   - Use terse bullets, copy‑paste commands (wrapped for ~400px width with line continuations), and avoid fluff.

---

# State of the Extractor Project

Date: 2025-09-18  
Owner: Engineering / Agents

## Executive Summary
- Green health: Classic UI mounts cleanly (no overlays), keyboard‑only flow works, search highlights and thumbnail badges render; core UX smokes pass locally.
- Pipeline OK: deterministic smokes pass (ReqIF v0 export, RTM v0 run summary, resume manifest). Artifacts written under `scripts/artifacts/`.
- Accurate PDF stages (01→14) remain healthy and deterministic; structured providers route via the unified CLI; Classic UI collaboration primitives are now aligned with the Happy Path and USER_FLOW.md.
- Single, paved surface preserved: `python -m src.cli extract` (fast|accurate) for operators; prototype UI acts as a client of the same pipeline (no new backend surfaces needed for MVP).

## Best‑in‑Class Research Question (Mil/Aero Engineering Docs)

Purpose
- Provide a single, durable question that guides priorities toward “best‑in‑class” status for scientific/engineering documentation at Mil/Aero scale.
- Keep scope aligned with the Happy Path (single CLI surface) and our collaboration‑first UX direction.

Core Question
- What capabilities must Extractor add or harden—beyond its staged, evidence‑rich pipeline; multi‑format parity; annotation loop; and Lean4 formalization—to be the best‑in‑class, open solution for very large engineering/scientific programs (10k+ pages, multi‑revision, compliance‑heavy), while preserving a minimal, easy‑to‑use surface for scientists and engineers?

Definitions (working)
- Best‑in‑class: Outperforms general‑purpose OCR/DocAI on engineering workflows by offering traceable artifacts, domain semantics (units/constraints), formalization, and cross‑document governance—without sacrificing simplicity.
- Minimal surface: One CLI (`python -m src.cli extract`), two PDF modes (fast/accurate), zero flags for structured providers; predictable Stage 07/10 outputs.

Today’s Strengths (anchor)
- Transparent, staged pipeline (01→14) with strict JSON artifacts and table evidence.
- Single CLI for PDF fast/accurate + structured providers; parity to a canonical schema.
- Annotation UI with iteration; thumbnails/pagination scaffolding.
- Lean4 proving stage to formalize and validate requirements (unique differentiator).

Gaps To Close (prioritized pillars)
- Scale & Resumability: stage checkpoints + idempotent resume; batch/orchestrator manifests and work queues.
- Cross‑Doc Traceability & Conflicts: RTM links across documents/revisions; conflict detection (duplicate clusters; numeric/unit mismatches).
- Standards & Interop: ReqIF export (v0) + validator; OSLC links; scoped DOORS/Jama bridges.
- Engineering Semantics: units/uncertainty normalization; typed tables; glossary/ontology mapping hooks.
- MBSE & Test Alignment: minimal SysML/XMI import; requirement→test stub linkage.
- Governance & Security: RBAC/SSO stub; audit log; redaction pipeline; air‑gap recipe.
- Observability: run manifests; per‑stage metrics/SLOs; failure taxonomy; artifacts index.

30/60/90 Outcomes (HP‑aligned)
- 30 days: RTM v0 in outputs; ReqIF export v0 + smoke; keep HP smokes green.
- 60 days: Conflict detection v1 (dup + unit); batch manifest + resume; table typing heuristics.
- 90 days: OSLC stubs + minimal SysML; audit log + redaction; run summary dashboard draft.

Evidence (acceptance signals)
- Smokes: parity 07/10; conflicts flagged; ReqIF round‑trip; RTM coverage in run summary.
- Operational: resume without recompute; per‑stage durations; invalid_json_count; fallback triggers.

References
- docs/03_guides/HAPPYPATH_GUIDE.md; docs/SMOKES_GUIDE.md; src/extractor/pipeline/docs/tasks/007_pipeline_cli_polish_and_guardrails.md; prototypes/tabbed/docs/tasks/001_ux_collaboration_and_ease_of_use.md

Stakeholder Prompt
- “Given our current strengths, do the pillar items above—implemented as optional, well‑smoked modules—close the gap to ‘best‑in‑class’ for Mil/Aero engineering documentation without increasing cognitive load for everyday users?”

## Fresh‑Eyes Assessment (2025‑09‑18)
- On trajectory: staged explainability + formalization already differentiate us vs generic Document AI.
- Ready for practitioners: single CLI surface; HP smokes green; Classic UI gaining collaboration markers (pagination/search/filters/review/notes/conflicts).
- Highest leverage next: RTM v0 + ReqIF v0 (interoperability), conflict detection v1 (units/dup), and batch/resume (operator reliability). These are modular and won’t expand the CLI surface.

## Recent Changes (2025‑09‑18)
- Stage 11 (Graph): reads Stage 08 theorems and emits offline JSON edges with `relationship_type: "proves"` for proved sections. Works without ArangoDB; aligns with artifact‑first debugging.
- Unified CLI fix: accurate PDF path now calls `python -m extractor.pipeline.run_all` (no extra `run` token). Prevents Typer argument error and unblocks CLI smokes.
- New smoke: `scripts/smokes/pipeline/smoke_stage11_proves_edges.py` — runs the single CLI with `--prove`, verifies 'proves' edges when proofs exist, otherwise records zero baseline. Artifact: `scripts/artifacts/stage11_offline_edges_summary.json`.
- Stage 08 (Lean4): when running in CI/offline, the pipeline now appends `--deterministic` to the Lean4 CLI via `LEAN4_CLI_CMD`. Smoke added: `scripts/smokes/pipeline/smoke_stage08_deterministic_env.py` (artifact: `scripts/artifacts/lean4_deterministic_env.json`).
- Stage 11 (Graph) schema/invariants: we now emit `11_graph_summary.json` with counts by type and a small set of invariant checks (v1). New smokes cover the summary and a proves‑only offline path (no embeddings).
- Stage 10 units normalization (optional): when `pint` is available, Stage 10 extracts and normalizes `<number> <unit>` tokens and attaches a `units` array per object. Stage 11 adds `conflicts_with` edges when SI‑normalized values disagree beyond a tolerance. Smokes added.
- Exporters: JSON‑LD graph exporter (v0) and ReqIF exporter smoke now validate structure. Smokes and artifacts recorded.
- Online Smokes (Opt‑In): added three tiny, cached LLM smokes (Stage 07 JSON‑strict, Stage 09 one‑section summary, Stage 11 single rationale). They auto‑skip when no provider keys are set and use litellm_cache to avoid duplicate spends.

## Competitive Landscape (2025‑09‑18)

Context: We re‑surveyed major document AI platforms and open tools against Extractor’s scope (staged pipeline, strict JSON artifacts, multi‑format parity, optional Lean4 proving, emerging ReqIF/RTM hooks).

- Cloud document AI
  - Azure AI Document Intelligence: OCR, tables/forms, custom models, query fields, multi‑page PDFs; strong enterprise integration but no native requirements formalization/ReqIF/RTM.
    - https://azure.microsoft.com/en-us/products/ai-document-intelligence
    - https://learn.microsoft.com/azure/ai-services/document-intelligence/overview
  - AWS Textract: OCR, forms/tables, queries/AnalyzeDocument; no formalization or ReqIF/RTM.
    - https://aws.amazon.com/textract/
  - Google Document AI: processors for OCR, forms, tables, procurement; no Lean4/ReqIF/RTM.
    - https://cloud.google.com/document-ai

- Open tools
  - Unstructured.io: modular ingestion/splitting/partitioning with many filetypes; good building block, not requirements‑aware.
    - https://unstructured.io/
  - GROBID: high‑quality scholarly PDF structuring (TEI/XML, headers/sections/tables/refs); no requirements pipeline.
    - https://github.com/kermitt2/grobid

- Requirements management (interoperability targets)
  - Jama Connect, Siemens Polarion, IBM DOORS Next: ReqIF import/export, RTM, change impact; expect pre‑structured inputs from parsing pipelines.
    - https://www.jamasoftware.com/solutions/reqif-requirements-exchange
    - https://www.ibm.com/products/engineering-requirements-management

Takeaway: We did not find a single system that combines robust AI extraction (tables/figures/sections) with native requirements formalization (Lean4‑like), ReqIF export, RTM enrichment, and cross‑doc change‑impact in one stack. Extractor’s staged, artifact‑first approach plus Lean4 is still a differentiator; hardening ReqIF/RTM/export and cross‑doc analytics remains the pragmatic path to “best‑in‑class” for Mil/Aero.

## Agent Memory (Lessons Learned)
- Location in this repo: `memory/README.md`
- Shared workspace variant: `/home/graham/workspace/experiments/memory/README.md`
- Purpose: a searchable “Lessons Learned” library (BM25 + graph recall with a FAISS proposer) to reduce cognitive load by reusing prior fixes, prompts, and playbooks.
- Usage (quick):
  - Recall last helpful lesson from logs: `make lessons-recall-last TAGS=cdp SCOPE=tabbed`
  - Direct recall: `uv run scripts/lessons/recall_agent.py --q "puppeteer connect hang" --scope tabbed --depth 2 --k 5 --json`
  - Add a new lesson after a fix: `uv run scripts/lessons/add.py --title "…" --problem "…" --playbook "…" --tags t1,t2 --scope tabbed`
- Recommendation: reference memory entries in issue descriptions and smokes to speed RCA and keep solutions consistent across providers and stages.

## Pipeline Stage Assessment (PDF Accurate Path)
- **01_annotation_processor** – Streams annotations from Marker snapshots, enriches with litellm heuristics, tags downstream relevance, and runs resource sampling. Tenacity retries protect LLM calls.
- **02_marker_extractor** – Wraps Marker CLI with resumable temp files and validates parsing reports; removes the legacy `langs` flag to stay in sync with surya APIs.
- **03_suspicious_headers** – Verifies ambiguous headings via vision-capable LLMs (preflight cache). Offline mode short-circuits to structural heuristics when API keys are missing.
- **04_section_builder** – Builds nested sections from verified blocks, preserving provenance (`stage03_or_fallback`) and supporting fallback heuristics for degraded PDFs.
- **05_table_extractor** – Camelot lattice strategies with per-table fragmentation scoring, header coalescing, sanitized vs raw payloads, table imagery via PyMuPDF, and detailed strategy diagnostics. Fragmentation smokes ensure quality-aware fallbacks are ready.
- **06_figure_extractor** – Extracts figure crops with configurable padding, batches VLM captions (optional), and records retry/latency metrics.
- **07_reflow_section** – Async LLM reflow with strict JSON schema, table image embedding, automatic fallback text blocks, and vision preflight to avoid unsupported models.
- **08_lean4_theorem_prover** – Pipes Stage 07 requirements through Lean4 CLI, logging proof attempts and exposing skip/prove toggles for CI.
- **09_section_summarizer** – Generates summaries after theorem proving, merging proof status and reporting coverage metrics consumed by `cli_happy`.
- **10_arangodb_exporter** – Flattens documents deterministically, validates against gold invariants, and honors `skip_export` / `fast_embeddings` toggles for offline runs.
- **11_arango_create_graph** – Builds similarity edges via FAISS when available; falls back to NumPy. Smokes assert graph cardinality and edge presence.
- **12_insert_annotations** – Inserts Stage 01 annotations into Arango with idempotent upserts and conflict logging.
- **14_report_generator** – Aggregates run diagnostics, resource samples, and operator-friendly metadata into the final reports consumed by pipeline dashboards.

## Structured Providers & Conversion Layer
- **Router** – `pipeline_router` maps file types to `STRUCTURED_PIPELINES`, invoking `run_structured_pipeline` with deterministic skips and normalized outputs.
- **HTMLProvider** – BeautifulSoup + optional Trafilatura path; preserves headings, tables, forms, images, generator metadata, and builds a hierarchy/keyword index.
- **DOCXProvider** – Uses docx2python + python-docx for images/comments; promotes numbered headings, merges tables when Claude analysis is enabled, and tags mangled-docx fallbacks for Stage 05 reuse.
- **PPTXProvider** – python-pptx ingestion with slide hierarchy, notes folding, embedded image export, and optional AI table merge analysis; captures slide metadata (count, dimensions).
- **SpreadsheetProvider** – Normalizes multi-sheet context, preserves header rows, and emits grid tables suited for Stage 10 comparisons.
- **EPUB/RST/XML/Markdown Providers** – Map native structures to `UnifiedDocument`, handling TOC fallbacks, directive parsing, wrapped roots, and consistent paragraph/list semantics.
- **Fast DOCX→PDF fallback** – Structured pipeline can auto-convert mangled DOCX into PDF and rerun accurate stages; smoke `smoke_docx_fallback_success.py` checks diagnostics and artifacts.

## Smoke Coverage Snapshot
- **Pipeline Stages** – `scripts/smokes/pipeline/smoke_stage0X_*.py` cover every stage (offline toggles, strict JSON validation, table fragmentation, figure propagation, graph edges, report integrity).
- **Provider Parity** – Per-format parity smokes compare structured outputs with the PDF baseline (Stage 10 object counts, section hierarchy). `smoke_meta_parity_all_formats.py` orchestrates a CLI run per provider and diffs table/figure counts.
- **Capability** – HTML caption adjacency/nested lists/table headers; PPTX slide count vs sections, chart/table detection, notes extraction; DOCX numbering promotion + mangled diagnostics; Spreadsheet multi-sheet headers; EPUB TOC fallback; XML wrapped-root parsing.
- **CLI** – `smoke_cli_fast_pdf.py`, `smoke_cli_structured.py`, and `smoke_cli_structured_all.py` ensure `python -m src.cli extract` emits the expected artifact layout for fast PDFs and all structured inputs.
- **API / Arango** – Upsert/chat smokes confirm post-ingestion flows when ArangoDB is reachable.
- **Artifacts** – Smokes write JSON logs (e.g., `stage05_strategy_quality.json`, `meta_cli_parity_summary.json`, gold validation diffs) under `scripts/artifacts/` for operators.

## CLI Surfaces
- **Unified CLI** – `python -m src.cli extract <input> <out> [--mode fast|accurate]` routes PDFs to PyMuPDF fast mode or to the `run_all` accurate path (with deterministic skips), and auto-dispatches structured formats to their providers.
- **Operator Tools** – `pipeline-run` (`cli_mode.run`) wraps fast vs accurate execution with optional JSON envelopes; `pipeline-run-all run` executes the Typer pipeline (stages 01→14); `pipeline-happy` remains for deterministic validation/score aggregation and is used by `cli_happy`.
- **Automation Hooks** – Make targets (`make smokes-pipeline-happy`, `make quick-pipeline`, `make extract-fast …`) and VS Code tasks provide one-click validation loops.

## Known Gaps & Watchlist
- Stage 05 now wires the fragmentation detector into a Camelot fallback loop and tracks per-page metrics; next, extend the path to trigger vision transcription when all lattice/stream strategies still fragment.
- Happy Path documentation (`docs/03_guides/HAPPYPATH_GUIDE.md`) still references the legacy gamified CLI verbs; align with the unified CLI terminology.
- Accurate PDF runtime remains heavy; continue using the fast toggles for dev and profile Stage 01 concurrency on larger PDFs.
- OCR remains English-only; add language detection + surya compatibility when multi-language support becomes a requirement.

## Recommended Next Actions
- Validate Stage 05 fallback metrics against larger PDFs and extend the retry path with a vision transcription option for persistent fragmentation, building on the new smoke coverage.
- Refresh Happy Path documentation to highlight `python -m src.cli extract`, `pipeline-run`, and the structured pipeline flow.
- Expand PPTX smokes with real-world templates to harden notes/chart extraction beyond synthetic samples.
- Consider folding provider parity smokes into the local CI path once runtime is acceptable (<15 minutes).

## Reference Commands
- Accurate PDF pipeline:
  ```bash
  python -m extractor.pipeline.run_all run \
    --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf \
    --results data/results/pipeline \
    --offline --skip-llm03 --skip-descriptions06 \
    --summary-only07 --skip-proving08 \
    --skip-export10 --fast-embeddings10 --skip-graph11
  ```

---

## Research Method & Competitive Update (2025‑09‑19)

Method
- Local MCP tools (brave‑search, perplexity‑ask) to refresh primary docs; synthesized into Happy‑Path recommendations (no new CLI surface).

Updated Competitive Pointers
- Label Studio — hotkeys/keymaps for review speed: https://labelstud.io/guide/hotkeys; https://labelstud.io/guide/labeling
- PSPDFKit — annotation shortcuts (copy/cut/paste/duplicate): https://pspdfkit.com/guides/web/annotations/create-edit-and-remove/cut-copy-duplicate/
- PDF.js — search/find controller patterns: https://github.com/mozilla/pdf.js/issues/12190
- ReqIF tools — round‑trip & validators: https://www.reqif.academy/software/reqif-studio/; https://github.com/ebroecker/pyreqif; https://github.com/strictdoc-project/reqif
- DOORS Next — ReqIF import/export: https://www.ibm.com/docs/en/engineering-lifecycle-management-suite/doors-next/7.0.3?topic=files-importing-exporting-reqif
- OSLC RM 2.1 — spec/shapes: https://docs.oasis-open-projects.org/oslc-op/rm/v2.1/requirements-management-spec.html

Happy‑Path Next Steps (evidence‑backed)
1) ReqIF export v0: emit from Stage 10; smoke round‑trip (ReqIF Studio).
2) RTM v0: produce CSV/JSON + include counts in run summary.
3) OSLC link stubs: minimal service doc + link POST, local index; smoke GET/POST.
4) Conflicts v1 (dup + units): UI panel + conflicts_{docId}.json; smoke resolved toggle.
5) Batch/resume: stage checkpoints + `--resume`; smoke start‑stop‑resume.
6) Review ergonomics: hotkeys ([, ], N, ?, Esc), focus/ESC; smoke keyboard‑only flows.

Acceptance Signals
- ReqIF opens; RTM counts present; OSLC link round‑trip; conflicts saved; resume skips recompute; keyboard smokes pass; no dev overlays; toolbarClear=true.
- Fast PDF text-only:
  ```bash
  python -m src.cli extract data/input/pipeline/BHT_CV32A65X_marked.pdf out_fast --mode fast
  ```
- Structured sample (HTML):
  ```bash
  python -m src.cli extract \
    data/results/pipeline/01_annotation_processor/BHT_CV32A65X_marked_clean.html \
    out_html
  ```
- Meta parity smoke:
  ```bash
  uv run scripts/smokes/pipeline/smoke_meta_parity_all_formats.py
  ```
- Stage 05 quality smoke:
  ```bash
  uv run scripts/smokes/pipeline/smoke_stage05_strategy_quality.py
  ```

---

## Auto‑Run Validation — 2025‑09‑19

- UX Health
  - Command:
    ```bash
    BASE_URL=http://127.0.0.1:8080/main \
    node scripts/ux_check_broken.mjs
    ```
  - Status: OK (no overlays; toolbarClear=true; pointer draw OK)
  - Latest log: scripts/artifacts/ux_check_2025-09-19T22-06-06-361Z.log

- UI Smokes (subset)
  - Keyboard core: OK — scripts/smokes/ui_keyboard_core.mjs
  - Search highlight + thumb: OK — scripts/smokes/ui_search_highlight_thumb.mjs

- API Smokes
  - OSLC stub: OK — service GET + link POST/GET (base=http://127.0.0.1:8000)
  - Conflicts save: OK — conflicts_docdemo.json under scripts/artifacts/

- Pipeline Smokes
  - ReqIF v0 export: OK — scripts/artifacts/export.reqif
  - RTM v0 report: OK — scripts/artifacts/rtm_smoke/final_report.md
  - Resume manifest: OK — run_all skipped unchanged stages; final_report.md present

Artifacts for this run are stored under scripts/artifacts/ with timestamps.
