RINSE/REPEAT Test Loop — Extractor

Goal
- Drive the Tabbed UX and API smokes to green with deterministic, timeout‑guarded loops. After 3 failed iterations, auto‑prepare a single‑file review bundle and hand off to a larger/smarter model.

Pre‑reqs
- Venv + env loaded:
  - `source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a`
- Chrome with CDP (optional but preferred):
  - `google-chrome --remote-debugging-port=9222` (or Browserless WS)
- Live servers (preferred via VS Code Tasks):
  - `Prototype: Preview (0.0.0.0:8080)` or `Prototype: Dev (vite on 8080)`
  - `Backend: FastAPI (8000)` or `Run: Backend + Preview`

Always‑On CDP Rule
- Use the Chrome DevTools MCP/CDP gate for UX verification whenever possible.
- Artifacts (screenshot + log under `scripts/artifacts/`) are the source of truth.

Loop A — UX Health (center‑pane) [non‑CDP or CDP]
1) Typecheck/build (timeouts):
   - `cd prototypes/tabbed/html && timeout 180s npm run -s typecheck && timeout 420s npm run -s build`
2) Preview server (8080) and gate with timeout:
   - Non‑CDP: `BASE_URL=http://127.0.0.1:8080/main timeout 120s npm run -s ux:check`
   - CDP (preferred): `BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser timeout 120s npm run -s ux:check:cdp`
3) Accept only if: `appReady=true`, `rootMounted=true`, `uiReady=true`, `toolbarClear=true`, `pointerDrawOk=true`, `consoleErrorsHard=0`, and no dev overlay.
4) Iterate micro‑fixes and repeat up to 3 times.
5) If still failing after 3, run the escalation bundle (see below).

Convenience targets
- `make rinse` (non‑CDP) or `make rinse-cdp` (with `BROWSERLESS_WS`): wraps `scripts/ci_rinse_repeat.sh`.
  - Attempts: `ATTEMPTS=3 make rinse`

Loop B — Full UX/API Smokes
1) Ensure live dev servers are running (Preview + Backend).
2) Run fast pass (skips some heavy steps):
   - `SMOKES_FAST=1 timeout 600s node scripts/smokes/all.mjs`
3) If green, run full suite:
   - `timeout 1800s node scripts/smokes/all.mjs`
4) Iterate micro‑fixes and repeat up to 3 times.
5) If still failing after 3, run the escalation bundle.

Make targets
- Quick loop: `make smokes-rinse` (fast pass) or `make smokes-rinse-full` (full suite)
  - CDP attach is auto‑discovered by `scripts/ux_check_cdp_auto.mjs` within the suite when required.

Escalation: one‑file review bundle
- Build and gist a single‑file package for external review:
  - `bash scripts/ci_rinse_repeat.sh --bundle` (runs a UX loop; also writes the bundle)
  - Output file: `scripts/artifacts/EXTRACTOR_EXTERNAL_REVIEW.md`
  - Gist URL (if gh authed or `GITHUB_TOKEN` set): `scripts/artifacts/EXTRACTOR_EXTERNAL_REVIEW.url`
  - Include the last failing UX artifact pair (PNG + LOG) in your review request.

Acceptance (Definition of Done)
- UX health: center‑pane gate passes with CDP artifacts attached.
- Full smokes: `node scripts/smokes/all.mjs` exits 0 (or `SMOKES_FAST=1` for fast lane).
- No dev overlays; no `console.error`/`pageerror` from the app; document/script/stylesheet requests do not fail.

Notes
- The Tabbed UI renders a stub PDF when `/api/list` is not reachable, enabling the center‑pane checks to pass in preview‑only mode.
- Console 500s from preview‑only endpoints are tolerated in the log but do not count as `consoleErrorsHard`.

