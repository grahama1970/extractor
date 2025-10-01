RINSE/REPEAT Test Loop (Extractor)

Purpose
- Keep UI and pipeline gates green via a deterministic loop with strict timeouts.
- After 3 failed attempts, auto‑prepare a single‑file review bundle for a larger model.

Scope
- UX gates for the Tabbed prototype (`/main`) using Puppeteer and CDP.
- Optional pipeline sanity (`litellm_call.py sanity`) and offline smokes.

Commands (timeouts baked in)
- Typecheck: from `prototypes/tabbed/html`
  - `timeout 180s npm run -s typecheck`
- Build: from `prototypes/tabbed/html`
  - `timeout 420s npm run -s build`
- Preview + UX health (non‑CDP): from repo root
  - `BASE_URL=http://127.0.0.1:8080/main timeout 120s npm run -s ux:check`
- CDP attach variant (preferred): from repo root
  - `BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser timeout 120s npm run -s ux:check:cdp`

Loop Policy (3 attempts)
1) Make one minimal change.
2) Run typecheck/build and one UX gate (non‑CDP or CDP).
3) If failing, capture artifacts (screenshot + log under `scripts/artifacts/`).
4) Repeat up to 3 attempts (micro‑changes only). Do not batch edits.
5) If still failing, escalate:
   - Run `scripts/ci_rinse_repeat.sh --bundle` to create `EXTRACTOR_EXTERNAL_REVIEW.md` and a secret gist.
   - Include the last two artifact paths (PNG + LOG) in your review request.

Artifacts (always attach)
- `scripts/artifacts/ux_check_*.png`
- `scripts/artifacts/ux_check_*.log`

Escalation Bundle (single file)
- `scripts/artifacts/EXTRACTOR_EXTERNAL_REVIEW.md` assembled from:
  - Review header: `REVIEW_BUNDLE_PROMPT.md` (auto‑filled repo path + date)
  - Code bundles: `scripts/artifacts/extractor_pipeline_bundle.txt` and `scripts/artifacts/tabbed_bundle.txt`

Helper Script
- `scripts/ci_rinse_repeat.sh` implements the loop with strict timeouts and optional gist creation.
- Usage examples:
  - Default (2 attempts + bundle): `bash scripts/ci_rinse_repeat.sh`
  - CDP attach: `BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser bash scripts/ci_rinse_repeat.sh`
  - Skip bundle step: `bash scripts/ci_rinse_repeat.sh --no-bundle`

Notes
- CDP is preferred; treat CDP artifacts as the source of truth for pass/fail.
- The loop is green when: appReady=true, toolbarClear=true, pointerDrawOk=true, consoleErrorsHard=0, no dev overlay.

