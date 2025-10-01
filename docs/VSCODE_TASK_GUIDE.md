# VS Code Task Guide (Dev Servers + Sanity)

This guide keeps AGENTS.md concise by centralizing durable patterns for starting/stopping local servers with auto‑port selection and running a one‑shot UI sanity check.

- Auto‑port binding: prefer finding a free backend port starting from 8000 and a free Vite port starting from 8100. Avoid hard‑coding.
- CDP sanity: run a Puppeteer/Chrome sanity gate that fails on dev overlays, console/page errors, or missing core DOM markers. Save artifacts under `scripts/artifacts/`.

## Recommended Task Patterns

- Requirements UI (auto‑port): `scripts/dev_requirements.sh`
  - Binds FastAPI on the first free port ≥ 8000.
  - Starts Vite on the first free port ≥ 8100 (proxy→backend).
  - Prints the actual Open URL.
  - Runs a sanity smoke:
    - Console/overlay errors: `scripts/smokes/console_errors.mjs` (CDP when available; falls back to bundled Chromium).
    - Requirements DOM: `scripts/smokes/ui_requirements_pane_dom.mjs`.
  - Artifacts saved to `scripts/artifacts/`.

## Health Gate

- Quick local gate (no CDP required):
  
  ```bash
  BASE_URL=http://127.0.0.1:8080/main \
  npm run ux:check
  ```

- CDP attach variant (if Chrome is running with `--remote-debugging-port=9222`):
  
  ```bash
  BASE_URL=http://127.0.0.1:8080/main \
  BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser \
  npm run ux:check:cdp
  ```

## Tips

- If the dev overlay persists after a code change, clear Vite caches:
  
  ```bash
  rm -rf prototypes/tabbed/html/.vite prototypes/tabbed/node_modules/.vite
  ```
- Pass `RUN_SANITY=0` to skip the sanity step when iterating on styling.
- Prefer BASE_URLs that include the route (e.g., `/main`), and avoid appending route suffixes in smokes.
