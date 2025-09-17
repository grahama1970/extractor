# Fast Local Workflow (Human ↔ Agent)

This project optimizes for a fast, local loop: issues with screenshots, targeted smokes, minimal code changes, clear artifacts.

## Process Overview

1) Author an issue under `prototypes/tabbed/issues/` (include a screenshot and acceptance).
2) Agent normalizes the issue (formats acceptance) and scaffolds a smoke.
3) Agent writes/fixes code to make the smoke pass.
4) Run the full suite (saves artifacts). Paste paths back into the issue.

## Scaffolding (1 minute)

- VS Code: `Issue: Scaffold (tabbed)`
  - Creates `issues/NNN_slug.md` from template
  - Creates `scripts/smokes/issue_NNN.mjs` stub (initially failing)
  - Adds a VS Code task to run the smoke: `Smokes: Issue NNN`

### Multi-topic drafts (incoming/)

- Drop rough notes/screenshots into `prototypes/tabbed/issues/incoming/*.md`
- Run VS Code: `Issues: Promote incoming (tabbed)`
  - Splits draft into atomic issues under `prototypes/tabbed/issues/`
  - Scaffolds `scripts/smokes/issue_NNN.mjs` and adds VS Code tasks
  - Moves original draft to `incoming/archive/` with back-links

Issue template (fields): Context, Desired Behavior, Acceptance, Routes, Selectors, Smokes to add, Artifacts, Meta.

## Writing a smoke first (why)

> See also: `docs/SMOKES_GUIDE.md` for the comprehensive smoke authoring handbook.

- Forces clear acceptance (objective DOM/text/behavior)
- Guides the smallest code changes
- Produces artifacts (log/screenshot) you can paste in the issue

### Example (UI smoke)

```js
// scripts/smokes/issue_007.mjs
await page.goto(BASE+'/classic');
await page.waitForSelector('[data-testid="page-label"]');
// assert presence + tooltip
await page.waitForSelector('[data-testid="btn-add-annotation-top"]');
await page.hover('[data-testid="btn-add-annotation-top"]');
```

### Example (API smoke)

```js
// scripts/smokes/api_generate_model.mjs
// GET /api/health/llm -> expected model
// POST /api/ux/generate -> assert data.json.model === expected
```

## Implement the change (small patches)

- Keep UI changes minimal and targeted
- Add tooltips/titles for discoverability
- Use ShadCN loader components for non‑blocking feedback

## Run tests

- Quick checks:
  - `ruff check . && black --check . && mypy src && pytest -q`
  - `node scripts/smokes/api_generate_model.mjs`
- UX suite:
  - Start servers via VS Code (`Run Backend + Preview`) and ensure Browserless on 3000
  - `node scripts/ux_check_cdp_auto.mjs`
  - `node scripts/smokes/all.mjs`
  - Or one command: `make ci` (verifies servers/CDP, fast gates, API smokes, full suite)

Artifacts land in `scripts/artifacts/`.

## Preventing regressions

- Every issue adds/extends at least one smoke
- Smokes live in `scripts/smokes/` and are included in the suite
- `scripts/ci_local.sh` runs a full local gate:
  - Verifies dev server + CDP
  - Fast checks + API smoke
  - Full UX suite (saves artifacts)

## Backends/Frontends

- Backend (Python FastAPI): API smokes (no browser) validate behavior like `/api/health/llm`, `/api/ux/generate` and model attachment.
- Frontend (React + Tailwind + ShadCN): UI smokes validate routes, tooltips, thumbnails, non‑blocking loaders, dialogs, key interactions.

## Why this approach

- Keeps collaboration fast (no cloud CI required for heavy UX)
- Every change is verified by a small, reliable test and a screenshot/log
- Smokes are tiny and cheap to write; they capture user intent crisply
- The suite grows with your real needs and guards against regressions

## Commands

- Scaffold issue: VS Code `Issue: Scaffold (tabbed)`
- Local CI gate: `scripts/ci_local.sh`
- Run all smokes: `node scripts/smokes/all.mjs`
- Health gate: `node scripts/ux_check_cdp_auto.mjs`

## Getting Started (Prototype)

- Install deps: `cd prototypes/tabbed/html && npm ci`
- Dev server: `npm run dev` (Vite on 8080; `/api` and `/ws` proxied to backend)
- Preview build: `npm run build && npm run preview:8080`
- Backend (FastAPI): start via VS Code Task `Backend: FastAPI (8000)` or the compound `Run: Backend + Preview`

## CI Quick Start (UX + Smokes)

- Start Chrome CDP: `google-chrome --remote-debugging-port=9222` (or Browserless on 3000)
- Health (CDP): from repo root `npm run ux:check:cdp`
- Full smokes (requires live servers + CDP): `node scripts/smokes/all.mjs`
- One command local CI: `make ci`
  - Defaults: `BASE_URL=http://127.0.0.1:8080`, `CDP_URL=http://127.0.0.1:3000/json/version`
  - Override CDP via: `make ci CDP_URL=http://127.0.0.1:9222/json/version`

Artifacts are written to `scripts/artifacts/` (logs + screenshots).
