# 000 — Master Tasks List (Rebuild)

This is the authoritative, end‑to‑end plan for rebuilding `tools/gold_annotator_web` according to the prototype (image-30.png). Items include acceptance criteria and key implementation notes. Track progress by checking boxes.

## Phase 0 — Foundations

- [ ] Decide stack: Next.js (App Router) + React + Tailwind; overlay via `react-konva`; PDF via `pdfjs-dist` worker.
- [ ] Define persistent storage: IndexedDB via `dexie` for local autosave; file export/import JSON. Keep images on disk; do not store large blobs in DB.
- [ ] Define annotation schema (normalized coordinates): `{ id, pdfId, page, labelType, instanceId, notes, bbox:{x,y,w,h}, createdAt, updatedAt }`.
- [ ] Define Gold JSON schema (per-PDF export) and Export‑All bundle format (zip of per‑PDF JSONs).
- [ ] Establish keyboard shortcuts map and invariant UX behaviors (selection, escape, delete, duplicate).
- [ ] Developer ergonomics: Vite/Next dev with fast refresh; ESLint + Prettier; minimal CI check.

Acceptance
- [ ] One-page ADR in `docs/` capturing the above decisions.

## Phase 1 — Scaffolding & Layout

- [ ] Bootstrap clean Next.js app or reset existing to clean state.
- [ ] Global layout: three panels — Explorer (left, fixed width), Annotation (center, fluid), Inspector (right, fixed width).
- [ ] Add shared UI kit (Tailwind + shadcn/ui) and icon set.
- [ ] App shell with toasts, modal, and global hotkey handler.

Acceptance
- [ ] App renders three columns without errors; responsive down to 1200px width.

## Phase 2 — Explorer (Multi‑PDF)

- [ ] “Load PDF” control: select local file path or type path; compute doc id and store minimal metadata.
- [ ] List of PDFs with page counts and status chips (e.g., “unlabeled / partial / done”).
- [ ] Search/filter by name.
- [ ] Per‑item action: `export` (JSON), open in viewer; hover preview optional.
- [ ] “Export All” button visible at bottom.

Acceptance
- [ ] Add ≥2 PDFs; list shows names and counts; clicking selects active doc.

## Phase 3 — Viewer & Navigation

- [ ] Integrate `pdfjs-dist` with dedicated worker route; guard for server/client env.
- [ ] Render current page to canvas with scale slider; maintain device‑pixel ratio for crispness.
- [ ] Thumbnails strip with virtualization; page slider displaying current/total.
- [ ] Navigate via previous/next buttons and `[ / ]` keys; remember last page per PDF.
- [ ] Coordinate transforms util: map between canvas pixels and normalized [0..1] bbox.

Acceptance
- [ ] Can render and navigate a 1000‑page doc without crashes; memory stable (<~300MB in dev).

## Phase 4 — Boxes (Create/Edit)

- [ ] Draw rectangle via click‑drag; snap to bounds; minimum size threshold.
- [ ] Select, move, resize (corner/edge handles), and delete (Del/Backspace or toolbar button).
- [ ] Duplicate via HUD button or `Ctrl/Cmd+D`.
- [ ] Selection states with clear visuals; ESC clears selection.

Acceptance
- [ ] All operations update overlay immediately and preserve correctness on zoom.

## Phase 5 — Inspector (Labeling)

- [ ] Label Type dropdown (configurable list; default: Section, Table, Field)
- [ ] Instance ID input with validation (e.g., `sec-001`).
- [ ] Notes textarea (optional).
- [ ] “Generate JSON” action: preview derived Gold JSON for selected box/page.
- [ ] Hotkeys: numeric/letter shortcuts to set label type; Save (`Ctrl/Cmd+S`).

Acceptance
- [ ] Changing fields updates selected annotation; switching selection preserves edits.

## Phase 6 — Autosave & Persistence

- [ ] Debounced autosave to IndexedDB per change; global “All changes saved” indicator.
- [ ] Import/export annotations per PDF as `*.boxes.json` (normalized coordinates).
- [ ] Versioned store; safe migration when schema changes.
- [ ] Manual Save action writes `*.boxes.json` to disk when running in dev server context (API route) or downloads in browser‑only mode.

Acceptance
- [ ] Refreshing the page restores last state and selection.

## Phase 7 — Export & Gold

- [ ] Export per‑PDF Gold JSON using chosen schema.
- [ ] “Export All” creates a zip of Gold JSONs.
- [ ] Optional: Export annotated PDF with overlay boxes for visual review.

Acceptance
- [ ] Downstream consumer can parse Gold JSON; sample fixture added under `data/expected_json/`.

## Phase 8 — Performance & Large Docs

- [ ] Lazy render pages and thumbnails; prefetch adjacent pages.
- [ ] Cache last N rendered bitmaps; evict on memory pressure.
- [ ] Worker offloading for heavy rasterization.

Acceptance
- [ ] Smooth navigation at 60fps on average laptops for typical PDFs (5–20MB, 1k pages).

## Phase 9 — Quality & Tests

- [ ] Unit tests for transforms, schema, and reducers.
- [ ] Integration tests for autosave and import/export cycles.
- [ ] E2E (Playwright/Puppeteer): draw/move/resize/delete box; label and autosave; reload verifies persistence.
- [ ] Visual regression screenshots for main flows.

Acceptance
- [ ] CI job runs tests and basic lint; artifacts include screenshots on failure.

## Phase 10 — Debugging Environment

- [ ] Provide Dockerized Chrome with VNC/noVNC for shared debugging on the Ubuntu host.
- [ ] Document SSH port‑forwarding and URL.

Acceptance
- [ ] Maintainer can open DevTools remotely and reproduce UI issues.

## Phase 11 — UX Polish & Accessibility

- [ ] Clear empty states and loading skeletons.
- [ ] Keyboard navigation for panel focus and page changes.
- [ ] ARIA roles/labels for controls; contrast checks.
- [ ] Small animations (opacity/scale) for selections and HUD.

Acceptance
- [ ] Keyboard‑only session can complete core labeling flow.

## Phase 12 — Optional Intelligence

- [ ] Crop preview for selected box.
- [ ] Extract text/table from crop via server API or local parser; show result in HUD.
- [ ] Heuristic “Suggest label + JSON path” button; user can apply then edit.

Acceptance
- [ ] Non‑blocking: suggestions never overwrite without explicit user action.

## Phase 13 — Docs & Onboarding

- [ ] Update `README.md` with quickstart and known pitfalls.
- [ ] Add “How we store data” and “Coordinate system” docs.
- [ ] Record a short GIF demo and include in docs.

Acceptance
- [ ] A new contributor can get productive in <15 minutes.

## Open Questions (resolve before Phase 5)

- What is the exact label taxonomy for v1? (Section, Table, Field, …)
- Gold JSON contract with downstream tools — sample and validator available?
- Export All format preference — single combined file vs. zip of per‑PDF files?
- Is text search within PDFs required for v1 or deferred?
- Persistence: browser‑only acceptable, or do we need server‑side saves by default?

---

Changelog

- v0.1 (initial): Master list created; phases and acceptance criteria defined.

