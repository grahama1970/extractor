# User Flow Alignment — Happy Path & Smokes

Purpose
- Align the amended `USER_FLOW.md` with concrete Frontend and Backend changes.
- Enforce the Happy Path: one CLI surface (`python -m src.cli extract`) and deterministic smokes with saved artifacts per `docs/SMOKES_GUIDE.md`.
- Keep patches small and reversible; add or extend smokes first.

References
- Happy Path: `docs/03_guides/HAPPYPATH_GUIDE.md`
- Smokes Guide: `docs/SMOKES_GUIDE.md`
- Amended Flow: `USER_FLOW.md`

## 0) Preconditions
- [ ] Dev servers via VS Code Tasks: `Prototype: Dev (vite on 8080)` and/or `Run: Backend + Preview`.
- [ ] Health: `npm run ux:check` or `node scripts/ux_check_cdp_auto.mjs` passes (no overlays, no console/page errors).
- [ ] App‑ready marker present on all routes touched: `[data-testid="app-ready"]`.

---

## 1) Frontend Tasks (Classic/Tabbed/Dashboard)

- Unify toolbar & selectors across routes
  - What: Ensure `/main` (Classic), `/tabbed`, `/dashboard` expose the same stable hooks:
    - `top-toolbar`, `btn-first`, `btn-prev`, `pager-slider`, `page-label`, `btn-next`, `btn-last`
  - Acceptance: Paging works uniformly; toolbar never occludes canvas (marker `toolbar-clear=true`).
  - Smokes: `scripts/smokes/ui_pagination.mjs`, `scripts/ux_check_center_pane.mjs`.

- App‑ready marker everywhere
  - What: Set `[data-testid="app-ready"]` once the initial PDF and UI mount complete.
  - Acceptance: Health gate waits for it; no Vite/React overlay present.
  - Smokes: `npm run ux:check` (saves `scripts/artifacts/ux_check_*.{log,png}`).

- In‑document search (pdf.js textContent)
  - What: Index current PDF via `pdfjs-dist` textContent; populate hits list with selectors:
    - `search-input`, `search-next`, `search-prev`, `search-hit` (with `data-page`, `data-snippet`).
  - Acceptance: Typing enables next/prev; cycling jumps pages and highlights.
  - Smokes: `scripts/smokes/ui_search_basic.mjs`.

- Filters gate overlays
  - What: Wire `filter-type-section|table|figure`, `filter-confidence`, `filter-owner` to the overlay render pipeline.
  - Acceptance: Toggling types and owner visibly changes overlays; slider hides low‑confidence items.
  - Smokes: `scripts/smokes/ui_filters_basic.mjs`.

- Review queue (Claim/Release)
  - What: `btn-claim`, `btn-release`, `status-badge`; persist to localStorage per‑doc.
  - Acceptance: Claim sets `assignee`; Release clears it; status badge updates and persists.
  - Smokes: `scripts/smokes/ui_review_queue.mjs`.

- Notes & @mentions
  - What: `notes-input`, `mention-suggest`, `mention-option`; suggestions pulled from recent reviewers.
  - Acceptance: Typing `@` opens list; selection inserts mention; notes persist per‑doc.
  - Smokes: `scripts/smokes/ui_notes_mentions.mjs`.
  
- Annotation grouping (multi-page tables)
  - What: Add a simple "group id" control in the right pane to link multiple annotations (e.g., table parts across pages). Single label per box remains; grouping joins them logically.
  - Acceptance: Setting a group id on two boxes marks them as grouped; filter/search can jump across grouped members; persisted per‑doc.
  - Smokes: extend `scripts/smokes/add_annotation_top_menu.mjs` to set a group id and verify it reflects in the list UI.

- Conflicts panel (MVP)
  - What: `conflicts-tab`, `conflict-item-*`, `btn-adjudicate`; client‑only duplicate/numeric mismatch stub.
  - Acceptance: Opening shows synthetic item; adjudicate toggles resolved state; jump highlights overlays.
  - Smokes: `scripts/smokes/ui_conflicts_panel.mjs`.

- Export actions (JSON / COCO)
  - What: Wire `btn-export-json` and `btn-export-coco-selection` to backend exports; keep a pure‑client fallback modal for JSON preview.
  - Acceptance: JSON dialog round‑trips; COCO selection endpoint called when backend is up.
  - Smokes: extend `scripts/smokes/issue_014.mjs` or add `scripts/smokes/ui_export_json.mjs`.

- CLI→UX handshake controls
  - What: `btn-load-pipeline-annos`, `btn-save-annotations`, `btn-upsert-pipeline` visible and usable.
  - Acceptance: Load annotates page; save writes local artifact; upsert shows success toast (backend optional; see §2).
  - Smokes: `scripts/smokes/ui_extract_load.mjs` (already present).
  
- Long‑run progress indicator
  - What: Non‑blocking progress bar/toast for pipeline execution (can exceed minutes). Reads `/api/pipeline/status` when a run is active and shows step + percentage.
  - Acceptance: Starting a run (see §2) shows status advancing through steps; UI remains responsive; completion dismisses indicator automatically.
  - Smokes: extend `scripts/smokes/ui_extract_load.mjs` to detect a visible progress element with current step text.

- Shortcuts panel
  - What: `?` opens help with paging, zoom, draw, HUD toggle.
  - Acceptance: Panel opens/closes with keyboard; focus trap holds.
  - Smokes: `scripts/smokes/ui_shortcuts_panel.mjs`.

- Per‑document persistence keys
  - What: Move from demo keys to `tabbed.review.<docId>.*` where `docId` comes from backend (`/api/pipeline/doc-id`).
  - Acceptance: Switching PDFs switches local state; keys visible in devtools Storage.
  - Smokes: small addition to `ui_review_queue.mjs` to assert doc‑scoped keys.

---

## 2) Backend Tasks (Tabbed FastAPI, Pipeline CLI)

- Single CLI surface (Happy Path)
  - What: Keep `python -m src.cli extract` as the only documented entry.
  - Acceptance: Fast PDF, Accurate PDF, and structured formats produce normalized Stage 07/10 artifacts as per the guide.
  - Smokes: pipeline CLI smokes referenced in `docs/03_guides/HAPPYPATH_GUIDE.md`.

- Health and build metadata
  - What: `/api/build` returns `{ git, started_at }`; `/api/health/llm` exposes model if configured.
  - Acceptance: UI footer/overlay shows git short SHA; LLM health smoke passes or skips gracefully.
  - Smokes: `scripts/smokes/llm_health.mjs` (already present).

- UX generate endpoint
  - What: POST `/api/ux/generate` accepts crop box + model; uses LiteLLM when configured; falls back to canned output.
  - Acceptance: Works offline (mock) and online (provider); responds < 3s for mock.
  - Smokes: `scripts/smokes/api_generate_model.mjs`.

- Export endpoints
  - What: `/api/export/json`, `/api/export/pdf`, `/api/export/zip` stream artifacts with `no-store` headers.
  - Acceptance: JSON export round‑trip matches dialog; PDF route returns 200 with a non‑zero body.
  - Smokes: add `scripts/smokes/api_export_json.mjs` and `api_export_pdf.mjs`.

- Pipeline run integration (external)
  - What: `/api/pipeline/run-external` runs `run_all` with `--annotations-json` and deterministic flags; `/api/pipeline/status` and `/api/pipeline/result` expose progress.
  - Acceptance: Given a small bundle, run returns success with Stage 01 + 07 + (optional) 10 paths.
  - Smokes: `scripts/smokes/api_pipeline_job.mjs` (present) – extend to assert Stage 07 unified payload exists.
  - Notes: Expose coarse step progress for long PDFs so the UI can render a progress bar (see §1).

- Annotations save & upsert
  - What: `/api/annotations/save` writes canonical Stage‑01 JSON; `/api/pipeline/upsert` runs Stage 10 (fast embeddings) + 11 (graph offline) when configured.
  - Acceptance: Save writes file under the run dir; upsert returns path summary; both operate offline by default.
  - Smokes: `scripts/smokes/smoke_stage12_annotations.py`, `scripts/smokes/smoke_stage11_skip_graph.py`.

- Doc ID service for UI persistence
  - What: `/api/pipeline/doc-id?pdf_rel=...` returns a stable docId for localStorage scoping. Implement as a hash of file bytes to prevent accidental duplicates.
  - Acceptance: Frontend stores per‑doc keys using returned id.
  - Smokes: small API probe in `scripts/smokes/ui_extract_load.mjs` (or a dedicated `api_doc_id.mjs`).

---

## 3) Cross‑Cutting & CI Wiring

- UX Health Gate
  - Ensure `npm run ux:check` passes; artifacts saved to `scripts/artifacts/`.
  - Add `ux:check:cdp` variant to CI if not already.

- Typecheck (frontend)
  - Add `npm run typecheck` (`tsc --noEmit`) under `prototypes/tabbed/html` and use it in local CI before UX checks.

- Smokes registry
  - Add the new smokes to `scripts/smokes/all.mjs` with BASE_URL and CDP autodiscovery.

- Artifacts discipline
  - All smokes/screens save logs + screenshots with timestamps in `scripts/artifacts/`.

---

## 4) Acceptance Matrix (User Flow → Signals)

- Load PDF → `[data-testid="app-ready"]`, `[data-testid="top-toolbar"]`, `[data-testid="page-label"]`.
- Annotate → draw box, label appears; filters act on overlays.
- Generate → `/api/ux/generate` returns JSON or mock; dialog shows payload.
- Import pipeline annos → `btn-load-pipeline-annos` paints boxes.
- Save/Upsert → save writes Stage‑01; upsert returns Stage 10 summary.
- Review/Notes/Conflicts → state persists per‑doc; adjudication toggles.
- Export → JSON dialog round‑trips; COCO selection returns 200.

---

## 5) Definition of Done
- All listed UI selectors are present and functional on `/main`; mirrored on `/tabbed` and `/dashboard`.
- Health gate green; screenshots/logs attached.
- New/extended smokes pass locally; artifacts attached.
- CLI Accurate/Structured produce Stage 07 `unified_document` and Stage 10 flattened JSON as documented.
- No new CLI surfaces introduced; all endpoints degrade gracefully when optional services are absent.

---

## 6) Quick Commands

```bash
# Health (auto-CDP) — saves scripts/artifacts/ux_check_*.{png,log}
BASE_URL=http://127.0.0.1:8080 \
  node scripts/ux_check_cdp_auto.mjs

# CLI→UX handshake UI smoke
BASE_URL=http://127.0.0.1:8080/main \
  node scripts/smokes/ui_extract_load.mjs

# Accurate extract (Happy Path)
python -m src.cli extract \
  data/input/pipeline/BHT_CV32A65X_marked.pdf \
  data/results/pipeline \
  --mode accurate
```
