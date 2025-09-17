# Tabbed ↔ Pipeline Integration Tasks

Owner: pipeline team • Status: in progress

Guiding principles
- One button (UI) and one command (CLI) should run the same validated pipeline.
- Deterministic by default; tolerate content variance via gold invariants (no strict equality).
- Artifacts are easy to find: final report + validation summaries + run summary (score).

## Phase 1 — Extract + Auto‑Fill (UI happy path)
- [x] Bridge endpoint: POST `/api/pipeline/run-external` (normalized boxes → Stage‑01 JSON) → run_all with `--annotations-json --clean-pdf --validate` → return report/summary.
- [x] UI Extract button (Classic): POST run‑external; toast result.
- [x] UI Load pipeline annotations: fetch 04/05/06 JSONs, convert PDF points → normalized [0..1], union into `boxesByPage` tagged as auto.
- [x] Smokes: API bridge + CLI happy + run summary; wired in CI.

## Phase 2 — Save + Upsert to Arango (FAISS + relationships)
    - [x] Save consolidated annotations endpoint: POST `/api/annotations/save` { pdf_rel|pdf_path, boxes_by_page, results_dir? } → writes `results_dir/annotations.json` and Stage‑01 canonical `01_annotation_processor/json_output/01_annotations.json`.
    - [x] Upsert endpoint: POST `/api/pipeline/upsert` { results_dir } → runs Stage 10 export (fast embeddings) + Stage 11 graph; returns confirmation file paths.
    - [x] UI Save button and Upsert button (with toasts); links to Stage‑01 and graph confirmation.
    - [x] Smokes: API upsert smoke (`scripts/smokes/pipeline/smoke_api_upsert.py`) asserts confirmation JSONs and positive doc upsert count.

## Phase 3 — Chat pane (select PDFs, ask questions)
- [ ] Ensure Stage 10 writes `doc_id` + `doc_variant` in every object; prefer canonical identity.
- [ ] Chat API: POST `/api/chat/query` { doc_ids[], query, top_k? } → hybrid search (vector + BM25) over `pdf_objects`, return snippet list.
- [ ] UI: left rail multi‑select (ShadCN Indicator green=upserted, grey=not); chat panel with results list and snippets.
- [ ] Smokes: API chat smoke (nonempty answer for seed query).

## DX / Docs / Tasks
- [x] One‑liner: `make steps-happy` prints report/summary.
- [x] docs/steps updated for external annotations + deterministic flags.
- [ ] VS Code Task: "Pipeline: Run from external annotations" (run_all with skip‑01 flags).
- [ ] Unify backends: import pipeline routes into the main prototype server; remove duplicate standalone if not needed.
- [ ] Provider smokes for docx/html/pptx fixtures.

## Acceptance (Happy path)
- [x] BHT 2‑page PDF passes gold invariants for 01, 02, 03, 04, 05, 06, 07, 09, 10, 11, 14.
- [x] scripts/artifacts/run_summary_happy.json contains { ok: true, score: number }.
- [x] data/results/pipeline_happy/final_report.md exists.
