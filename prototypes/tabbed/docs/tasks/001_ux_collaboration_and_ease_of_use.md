# Tabbed UX — Collaboration & Ease‑of‑Use (Happy Path Aligned)

Purpose
- Minimize cognitive load for scientists/engineers on large programs.
- Prioritize a small, predictable surface and collaborative workflows.
- Sequence improvements through atomic tasks with objective acceptance and smoke artifacts, applying changes only when the slice is ready to ship.

Scope guard
- Respect Happy Path: no new CLI surfaces; UI focuses on pagination, search, filters, conflict view, and lightweight review.
- No backends required beyond existing FastAPI dev server (scripts/dev.sh) and current endpoints.

State persistence (local-only)
- Keep storage client-side: `localStorage` keys must use the `tabbed.review.` prefix.
- Reviewer identity: store the current name under `tabbed.review.identity`.
- Per-document data (assignments, notes, adjudication) should serialize to JSON blobs keyed as `tabbed.review.<docId>.assignments`, `...notes`, and `...conflicts`.
- Changes must remain optional—absence of keys should fall back to default UI state.

## 0) Preconditions
- [ ] Dev servers running via VS Code Task `Prototype: Dev (vite on 8080)` or `npm run preview:8080`.
- [ ] Health: `npm run ux:check` passes (no overlays, no console errors).
- [ ] Pipeline pointer endpoint available: `/api/pipeline/latest` and `/api/pipeline/latest-set` (UI can load stage artifacts).

## 1) Pagination & Navigation (Keyboard‑first)
- Outcome: Consistent paging in all layouts; toolbar never occludes canvas.
- UI markers:
  - `[data-testid="pager-prev"]`, `[data-testid="pager-next"]`
  - `[data-testid="page-number"]` (text content), `[data-testid="page-slider"]`
- Acceptance:
  - Left/Right buttons page; `[` and `]` keys work; page number updates.
  - Top toolbar is sticky and does not overlap rendered canvas.
- Smokes:
  - `scripts/smokes/ui_pagination.mjs` (saves `scripts/artifacts/ui_pagination.png` and log)
- [ ] Implement

## 2) Search (Doc & Collection)
- Outcome: Left sidebar Search tab supports:
  - In‑document text search with highlight and next/prev.
  - Collection search across loaded PDFs (name + simple text index) with result list.
- UI markers:
  - `[data-testid="search-input"]`, `[data-testid="search-next"]`, `[data-testid="search-prev"]`
  - Results list items: `[data-testid="search-hit"]` with `data-page` and `data-snippet`.
- Acceptance:
  - Typing query enables buttons; next/prev cycles hits; jumping updates page and highlights.
  - Collection mode filters the Files list by query.
- Smokes:
  - `scripts/smokes/ui_search_basic.mjs` (artifact `scripts/artifacts/ui_search_basic.png`)
  - [planned] `scripts/smokes/ui_search_hits_indexing.mjs` (asserts hit count and highlight)
- [ ] Implement

## 3) Filters (Type, Confidence, Owner)
- Outcome: Quick filters reduce visual noise during review.
- Controls:
  - Type toggles: Section/Table/Figure/Text (`[data-testid="filter-type-*"]`)
  - Confidence slider: `[data-testid="filter-confidence"]`
  - Owner filter (Mine/Unassigned/All): `[data-testid="filter-owner"]`
- Acceptance:
  - Toggling types shows/hides matching overlays and list items.
  - Confidence threshold hides low‑score items.
  - Owner filter hides items not assigned to current user (localStorage‑backed identity stub).
- Smokes:
  - `scripts/smokes/ui_filters_basic.mjs` (artifact `scripts/artifacts/ui_filters_basic.png`)
- [ ] Implement

## 4) Conflict View (Duplicates & Numeric Mismatch)
- Outcome: A side panel lists likely conflicts; user can adjudicate.
- MVP logic (client‑only):
  - Duplicate cluster = near‑duplicate text (cosine over hashed shingles) across pages.
  - Numeric mismatch = same requirement key with differing numeric values/units.
- UI markers:
  - `[data-testid="conflicts-tab"]`, `[data-testid="conflict-item"]`, `[data-testid="btn-adjudicate"]`
- Acceptance:
  - Opening conflicts shows at least one synthetic demo item when backend absent.
  - Clicking a conflict jumps to page and highlights involved overlays.
  - Adjudicate toggles status to Resolved; persists in localStorage.
- Smokes:
  - `scripts/smokes/ui_conflicts_panel.mjs` (artifact `scripts/artifacts/ui_conflicts_panel.png`)
  - [planned] `scripts/smokes/ui_conflicts_load_and_resolve.mjs` (artifact saved under `scripts/artifacts/`)
- [ ] Implement

## 5) Review Queue (Claim/Assign)
- Outcome: Multi‑reviewer flow with low ceremony.
- Behavior:
  - Identity from localStorage (`reviewer_name`); default "Me".
  - Each annotation has `assignee` and `status` (Unassigned, In Review, Done).
  - Quick filters from §3 control visibility; list supports Claim/Release.
- UI markers:
  - `[data-testid="btn-claim"]`, `[data-testid="btn-release"]`, `[data-testid="status-badge"]`
- Acceptance:
  - Claim sets assignee; Release clears it; status badge updates; persists per‑doc in localStorage.
- Smokes:
  - `scripts/smokes/ui_review_queue.mjs` (artifact `scripts/artifacts/ui_review_queue.png`)
- [ ] Implement

## 6) Notes & @Mentions (Local)
- Outcome: Lightweight comments per annotation with simple @mention autocomplete from recent reviewers.
- UI markers:
  - `[data-testid="notes-input"]`, suggestion list `[data-testid="mention-suggest"]`
- Acceptance:
  - Typing `@` opens suggestions; selecting inserts `@name`.
  - Notes persist in localStorage (per‑doc, per‑annotation).
- Smokes:
  - `scripts/smokes/ui_notes_mentions.mjs` (artifact `scripts/artifacts/ui_notes_mentions.png`)
- [ ] Implement

## 7) App‑Ready Marker & Health Gate Hooks
- Outcome: Deterministic readiness for automated checks.
- Markers:
  - Root: `[data-testid="app-ready"]` set when initial PDF and UI mount complete.
  - Toolbar clear check: `[data-testid="toolbar-clear=true"]` if canvas is unobstructed.
- Acceptance:
  - `npm run ux:check` waits for app‑ready and passes with no overlays or console errors.
- Smokes:
  - Use existing `npm run ux:check` and save artifacts `scripts/artifacts/ux_check_*.{log,png}`.
  - CDP attach option: `node scripts/ux_check_cdp_auto.mjs` (saves artifacts under `scripts/artifacts/`).
- [ ] Implement

## 8) Shortcuts & Help
- Outcome: Discoverable keyboard shortcuts and mode hints.
- UI markers:
  - `[data-testid="help-shortcuts"]`
- Acceptance:
  - Pressing `?` opens a shortcuts panel listing paging, zoom, draw, HUD toggle.
- Smokes:
  - `scripts/smokes/ui_shortcuts_panel.mjs`
- [ ] Implement

## 9) Definition of Done (UX slice)
- [ ] Pagination/search/filters/conflicts/review/notes implemented with markers above.
- [ ] Health gate passes; artifacts saved.
- [ ] All new smokes pass locally; artifacts attached under `scripts/artifacts/`.
- [ ] No prototype code paths require new backend endpoints for MVP (pipeline bridge endpoints under `/api/pipeline/*` already exist for dev convenience).

## 10) Pipeline Integration Checks (Happy Path glue)
- Outcome: UI actions reflect pipeline artifacts and vice‑versa.
- Actions & endpoints:
  - Save annotations → POST `/api/annotations/save` (writes UI‑normalized + Stage‑01 JSON)
  - Run pipeline (UI) → POST `/api/pipeline/run-external` (writes `latest_results.json` pointer)
  - Load pipeline annos → GET `/api/pipeline/latest` → read 04/05/06 via `/api/artifacts/file?path=...`
  - Upsert graph → POST `/api/pipeline/upsert` (Stage‑10/11)
- UI markers:
  - `btn-save-annotations`, `btn-extract-pipeline`, `pipeline-progress`, `btn-load-pipeline-annos`, `btn-upsert-pipeline`
- Smokes:
  - `scripts/smokes/ui_progress_pipeline_run.mjs` (progress banner visible)
  - `scripts/smokes/ui_load_pipeline_annos_from_latest.mjs` (overlays or request‑trail acceptance)

## 10) Stretch (deferred; do not implement yet)
- Cross‑doc compare view (diff pane).
- ReqIF export from selected requirements.
- RBAC/SSO; server‑side comments.

---

## Quick‑Run (once implemented)
```bash
BASE_URL=http://127.0.0.1:8080 \
  npm run ux:check && \
BASE_URL=http://127.0.0.1:8080/main \
  node scripts/smokes/ui_pagination.mjs && \
BASE_URL=http://127.0.0.1:8080/main \
  node scripts/smokes/ui_search_basic.mjs && \
BASE_URL=http://127.0.0.1:8080/main \
  node scripts/smokes/ui_filters_basic.mjs && \
BASE_URL=http://127.0.0.1:8080/main \
  node scripts/smokes/ui_conflicts_panel.mjs
```
