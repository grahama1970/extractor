# UX Critique 002 — Tabbed Prototype (Classic Layout)

Author: External Review Prep
Date: 2025‑09‑20
Scope: prototypes/tabbed/html (UI), prototypes/tabbed/api (API), scripts/* (smokes/dev)

---

## 0) Executive Summary
The Classic layout renders but has regressions and contract drift with our smokes. Focus on fixing a small set of deterministic issues that block reviewers:

- Center viewer “canyon” (wide blank gutter) due to layout/overlay coupling — Fix: single viewer row + absolute HUD.
- Missing/incorrect test selectors (`inspector-pane`, requirements pane) — add to match smokes.
- Undefined handlers referenced in file list (hover/checkbox) — replace with existing helpers.
- Export payload mismatch + server export loop bug — outputs can be silently wrong.
- BuildChip uses wrong endpoint — hides useful diagnostics.

A minimal patch set (UI + API + smokes) will bring the gate to green for external review.

---

## 1) Repro (deterministic; no task scripts)
```bash
# Kill and clear
fuser -k 8080/tcp 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true
rm -rf prototypes/tabbed/html/.vite prototypes/tabbed/html/node_modules/.vite prototypes/tabbed/node_modules/.vite

# Backend (fixed port)
source .venv/bin/activate
SERVER_PDFS_ROOT=$PWD/data/input/pipeline \
python -m uvicorn prototypes.tabbed.api.server:app --host 0.0.0.0 --port 8025

# Frontend (proxy → 8025; fixed port)
cd prototypes/tabbed/html
VITE_API_PROXY=http://127.0.0.1:8025 \
npm run dev -- --force --port 8080 --strictPort

# CDP attach once Chrome is running
google-chrome --headless=new --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 --no-sandbox --disable-gpu about:blank &
BASE_URL=http://localhost:8080/main \
BROWSERLESS_DISCOVERY_URL=http://127.0.0.1:9222/json/version \
node scripts/ux_check_cdp_auto.mjs
```
Artifacts: scripts/artifacts/ux_check_cdp_*.{log,png}

---

## 2) Blocking Issues (ordered by risk)

### A. API: Export loop bug and payload normalization (crasher + silent-wrong)
- `api_export_pdf` in `prototypes/tabbed/api/server.py` uses `pnum/arr` after the loop due to indentation; only the last page is annotated or crashes when empty.
- UI sends raw `{x,y,w,h}` arrays to `/api/export/pdf|zip`. Server expects `bounding_box/bbox`.

Action:
- Fix loop indentation; normalize bbox once server-side; map UI payload to `{bounding_box:[x,y,w,h]}` client-side.

Acceptance:
- Export produces visible overlays for multiple pages; no exceptions in server logs.

### B. UI: Undefined handlers in file list (visible crash)
- `fetchDbStatusForRel`, `toggleSelectRel` are referenced but not defined.

Action:
- Replace with existing helpers: use `refreshDbStatus()` and inline checkbox toggle with `ensureDocId()`.

Acceptance:
- Hovering a file row and toggling selection does not throw; dev console clean.

### C. UI: Selector drift vs smokes (false negatives)
- Smokes expect `[data-testid="inspector-pane"]` and a Requirements pane header; UI lacks those.

Action:
- Add `data-testid="inspector-pane"` to the inspector root; (optional) add a slim Requirements header with `data-testid="req-pane"` and `req-refresh` even when empty.

Acceptance:
- `ui_inspector_pane_present.mjs` & `ui_requirements_pane_dom.mjs` pass; CDP gate stays green.

### D. UI: Center “canyon” (layout)
- Middle container stacks columns; HUD not absolutely layered over canvas.

Action:
- Ensure a single viewer row: left rail (fixed width) + viewer (flex-1, `position:relative`), with HUD overlay `position:absolute; inset:0`.

Acceptance:
- Pixel metric `gutterPx ≤ 24` (scripts/artifacts/gutter_metrics_review.json); CDP gate green.

### E. BuildChip mismatch (diagnostic)
- App.tsx fetches `/build.json` and `built_at`; server exposes `/api/build` with `started_at`.

Action: update endpoint/field.

Acceptance: chip shows `git · HH:MM:SS` while server runs.

---

## 3) Concrete Patches (high‑impact)

### API (server.py) — export loop, litellm guards, artifact root safety
- Fix `api_export_pdf` inner loop indentation
- Guard `litellm_call` imports (return 503 when unavailable)
- Restrict `/api/artifacts/file` to `ARTIFACTS_ROOT` via `Path.resolve().relative_to(root)`

### UI (ClassicLayout.tsx)
- Add `data-testid="inspector-pane"`
- Replace undefined handlers:
  - `onMouseEnter={()=>{ if (it.rel) refreshDbStatus(); }}`
  - Checkbox `onChange` resolves `docId` and toggles `selectedDocIds`
- Normalize client export payload to `{bounding_box}` for `/api/export/(pdf|zip)`
- (Optional) Requirements header: `[data-testid="req-pane"]` with a `Refresh` button stub
- Center layout: viewer row with absolute HUD

### App.tsx — BuildChip
- Fetch `/api/build`; read `started_at`.

### Smokes
- `console_errors.mjs`: when launching bundled Chromium, call `browser.close()` (not `disconnect()`)
- `ux_check_cdp_auto.mjs`: inline a minimal fetch check if `scripts/ux_check_cdp.mjs` is missing

---

## 4) Acceptance & Gates

Run on http://localhost:8080/main with CDP attach.

- Typecheck: `cd prototypes/tabbed/html && npm run typecheck`
- CDP health: `node scripts/ux_check_cdp_auto.mjs`
  - navOk=true, overlayPresent=false, rootMounted/uiReady=true, consoleErrors=0, failedRequests=0
- DOM smokes:
  - `node scripts/smokes/ui_inspector_pane_present.mjs` → pass
  - `node scripts/smokes/ui_requirements_pane_dom.mjs` → pass (header visible; may be empty)
- Pixel metric:
  - `gutter_metrics_review.json` recorded; `gutterPx ≤ 24`
- Export E2E (manual once):
  - Trigger export; open artifact; verify overlays drawn on multiple pages

---

## 5) Risks & Rollback
- Vite optimizer drift: the manual repro nukes caches and uses `--force`; if reviewers still hit drift, a hard refresh + re-run fixes it.
- Arango optionality: API endpoints return 503 when optional deps are missing; smokes avoid requiring DB.

---

## 6) Suggested Ownership / Small PR Plan
1. Server export & safety (API owner) — 1 PR
2. ClassicLayout quick fixes (UI owner) — 1 PR
3. Smokes hygiene (QA owner) — 1 PR

Total changes are small and isolated; the gates above keep us honest.

