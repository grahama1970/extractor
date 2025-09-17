# Lessons Learned (Running Notes)

This file captures repeat issues we’ve hit and the playbooks/checks that prevent them. Keep it short, actionable, and wired into tooling where possible.

## CDP (Chrome DevTools Protocol)

- Problem: Flaky CDP → agent can’t reach browser; runtime UI errors slip into PRs.
- Playbook (Always):
  - Stable endpoint: run headless Chrome on :9222 or Browserless on :3000.
  - Discover browser WS via `/json/version` (never hard‑code).
  - Bind servers to addresses the headless browser can reach (0.0.0.0 or loopback if co‑located).
  - Run a one‑shot console/pageerror smoke before merge.
- Repo automation:
  - `scripts/smokes/console_errors.py` (Playwright over CDP). Fails on console/page errors, saves screenshot and logs.
  - `scripts/dev.sh` supports:
    - `DEV_CDP_SANITY=1` → runs one‑shot console error smoke after Vite starts
    - `DEV_CDP_AUTOLAUNCH=1` → auto‑launch headless Chrome on :9222 if discovery is down
  - VS Code tasks: “Dev (Strict)” and “CI: Full Smokes (Headless CDP)”.
- Never again:
  - If UI shows blank or odd behavior, run `make smoke-ui` first; fix errors printed.

## Dev Proxy / Backend Port Drift

- Problem: Vite proxied /api to 8000, but backend started on another port.
- Playbook:
  - Prefer backend on 8000 during dev. If not, export `VITE_API_PROXY=http://127.0.0.1:<port>`.
  - Vite now auto‑detects 8000/8001 at startup; dev.sh passes the exact backend port to Vite.
- Never again:
  - Check dev logs: “proxy→ http://127.0.0.1:<port>”.
  - Curl `/api/list` on that port before debugging UI.

## Icon/Import Regressions (lucide‑react)

- Problem: Using an icon that’s not exported by the installed bundle → runtime ReferenceError.
- Playbook:
  - Prefer known icons already imported elsewhere (e.g., Download, FileText, Braces).
  - If adding new icons, import explicitly and run the console‑error smoke.
- Never again:
  - Add/change icons → run `make smoke-ui`.

## Export UX (Left Rail)

- Problem: Row actions too heavy; duplicated controls cause confusion.
- Playbook:
  - One tiny export icon per row (ghost, size=icon), reveal on hover/focus.
  - Export menu: JSON / Annotated PDF / Both (ZIP). Disable unless row is open.
  - No separate “…” icon; put Settings… as last menu item (disabled until needed).

## Quick Commands

- Strict dev (with CDP sanity):
  - `DEV_CDP_AUTOLAUNCH=1 DEV_CDP_SANITY=1 ./scripts/dev.sh`
- One‑shot UI error smoke (Playwright over CDP):
  - `make smoke-ui SMOKE_URL=http://127.0.0.1:8080/classic CDP_ORIGIN=http://127.0.0.1:9222`
- API sanity:
  - `curl http://127.0.0.1:8000/api/build`

## How to Contribute a Lesson

- Keep it short: problem → playbook → automation/guard → “never again” line.
- Prefer wiring a lesson to an executable: a smoke, a dev flag, or a VS Code task.
- Edit this file in PRs alongside the code that implements the guard.

