# AGENTS.md

## Repository Guidelines

Based on [OpenAI Prompting Guide](https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide).

### Agent Quickstart (Codex CLI)

* **Activation**: Start with the prompt:  
  `Activate the current dir as project using serena`
* **Planning**: Use `update_plan` for multi-step work.
* **Editing**: Apply changes via `apply_patch` (minimal, targeted diffs).
* **Search**: Use `rg` for fast project search.
* **Verify**: Run `pytest -q`, `ruff check .`, `black .`, `mypy src`.

#### Always Do This First

* Activate Serena project.
* Activate venv & load env:

  ```bash
  source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a
  ```

---

## UX-Specific Directives (Universal, Not Project-Specific)

* **Frameworks**: React + Tailwind + ShadCN. Responsive design, modern SVG icons, tasteful animations.
* **Verification**:
  * Use MCP Puppeteer to validate interactions.
  * Take screenshots; confirm no blank pages, React errors, or server issues.
  * Iterate until UX works as expected.
  
  
  **UX Health Checks (Browser Errors)**
  - Run a browser‑aware health gate that fails on client errors:
    - `npm run ux:check` (Puppeteer launcher)
    - `BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser npm run ux:check:cdp` (CDP attach)
  - Preconditions: start a live server via VS Code Task (prefer `Prototype: Dev (vite on 8080)`), or `npm run preview:8080`.
  - Failure criteria (non‑zero exit):
    - Vite dev overlay detected (`vite-error-overlay` in DOM)
    - `console.error` or `pageerror` events
    - Failed `document/script/stylesheet` network requests
    - App not mounted (`#root` empty) or key UI not present (`[data-testid="page-label"]`)
  - Artifacts (for issues/PRs): logs and screenshots in `scripts/artifacts/`.
  - Recommendation: add a small “app ready” marker on mount and wait for it in checks to reduce flakes.


  
  **Prototype Baseline E2E (Tabbed/Classic/Dashboard)**
  - Dev server required (prefer VS Code Task `Prototype: Dev (vite on 8080)` or `npm run preview:8080`).
  - Run:
    - `cd prototypes/tabbed/html && npm run e2e:base`
    - CDP variant: `BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser npm run e2e:cdp`
  - Coverage highlights:
    - Classic: draw via API and pointer (N to arm), duplicate/delete (UI and keyboard), pager ([, ])
    - Export/Generate JSON dialog opens (backend optional; WS→HTTP fallback handled)
    - Thumbnail modes: left/bottom/off via localStorage; HUD toggle via H; zoom slider present
  - Artifacts saved to `prototypes/tabbed/html/artifacts/` (when run from that dir) or `artifacts/` from repo root
* **Research**:
  * If blocked, perform external web research for visuals or code.
  * Use Context7 MCP for modern documentation.
* **Hot Reloading**: All UX must hot-reload for near real-time feedback.
* **User Collaboration**: Implement user requests unless they add brittleness or reduce usability. Recommend against with justification if so.

—

Always-On CDP/MCP Rule (must follow)
- Always use the Chrome DevTools MCP (CDP) for any UX debugging/verification:
  - Prefer `npm run ux:check:cdp` or `node scripts/ux_check_cdp_auto.mjs` while a live server is running.
  - Attach to an existing Chrome/Browserless via `BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser` when available.
  - From MCP: capture a full-page screenshot and list console messages for each route under test.
  - Treat the CDP artifacts as the source of truth for pass/fail.
  - If a non‑CDP gate is used first (e.g., `npm run ux:check`), follow it immediately with a CDP/MCP attach to validate and save artifacts.
  - If the MCP client reports the Chrome profile is already in use or refuses new sessions, restart the headless browser with `ch-headless` (defined in `~/.zshrc`). That helper stops any lingering Chromium/Chrome processes and relaunches `/snap/bin/chromium` headlessly on port 9222 with a clean user data dir.
  - After restarting Chromium, the Codex CLI must also restart the `chrome-devtools-mcp` server so it reattaches to the fresh browser. If MCP calls still fail after `ch-headless`, restart the Codex CLI (or its chrome-devtools MCP task) before retrying.

---

## Project Readiness (quick pass/fail)

- Dev (deterministic; no network):
  - make project-ready
  - Outputs: `PROJECT_READY.md` (with ✅/❌ summary) and `local/artifacts/mvp/mvp_report.json`.
- Deploy (live‑gated; fail on skips):
  - READINESS_LIVE=1 READINESS_E2E=1 STRICT_READY=1 make project-ready-live
  - Uses built‑in YouTube timedtext E2E; Ollama probe; fails on any skipped/stubbed checks.

Readiness Rule (no skips/triage)
- All smokes must pass before a project is ready to deploy. No triage, no skipping.
- Required gates (run locally or in CI):
  - Preview gate: `console_errors` with post‑ready scoring (hard=0), `no_preview_api_requests` (no `/api/*` after readiness), and `a11y_smoke` (logs only in preview).
  - Backend smokes: fast UI/API suite with the Tabbed backend running.
- One‑shot command for CI and pre‑merge: `make ci-rinse` (starts/stops preview, runs the three preview smokes, then backend fast smokes, and sanitizes artifacts). Any hard failure blocks deploy.


## Terminal Command Output (Agent)

- Always format multi-line terminal commands for a ~400px-wide terminal.
- Use line continuations (`\`) at logical breakpoints so commands copy/paste cleanly.
- Example style:

  ```bash
  BASE_URL=http://127.0.0.1:8080 \
  BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser \
  make smoke-ui-extract-load-cdp
  ```

---

## Verification & Integrity Policy (Agent)

The agent must not claim success without verifying the change in a browser context and saving artifacts. This policy applies to all UX work.

- Do not misrepresent state. If something was not run or is uncertain, say so.
- Before stating “fixed” for frontend/UX edits, always:
  - Type check: `cd prototypes/tabbed/html && npm run typecheck` (tsc --noEmit).
  - Load the route and verify no dev overlays (Vite or react‑swc).
  - Run the health gate: from repo root `npm run ux:check` (saves `scripts/artifacts/ux_check_*.{log,png}`).
  - For Classic `/main`, validate specifically:
    - Top toolbar is above the canvas and does not occlude it.
    - Pointer draw works (press `N`, drag → a box appears).
    - Thumbnails render in left‑rail and bottom filmstrip modes.
- Include artifact paths (screenshot + log) in the status update.

### Hard Rule: Screenshot + CDP per UI change

- After every change to anything under `prototypes/` (HTML/TSX/TS/Server):
  - Capture a full‑page screenshot and console log using the CDP/puppeteer gate.
  - Use one of:
    - `BASE_URL=http://127.0.0.1:<vite-port>/main node scripts/smokes/console_errors.mjs`.
    - `node scripts/ux_check_cdp_auto.mjs` (auto‑discovers CDP; saves artifacts under `scripts/artifacts/`).
  - Treat any Vite overlay, `console.error`, `pageerror`, or failed document/script/stylesheet request as a blocker.
  - Paste the two artifact paths (`*.png`, `*.log`) into the issue/PR update before claiming success.
- VS Code: see `docs/VSCODE_TASK_GUIDE.md` for the “Requirements: Dev (auto‑port)” launcher, which runs these checks automatically and fails fast with artifact links.

Artifacts (mandatory)
- For each route touched, attach at minimum:
  - One full‑page screenshot saved to `scripts/artifacts/` with a route tag (e.g., `main_*.png`).
  - The corresponding log file (e.g., `ux_check_*.log`) containing BASE_URL, overlay detection, pointer draw and any key metrics.
- If the fix concerns the center pane, ensure the log reports whether the toolbar occludes the canvas (toolbarClear=true) and whether pointer draw succeeded (pointerDrawOk=true).
- If a check fails locally, include the failing screenshot/log and do not claim success.

Fail conditions (must block)
- Dev overlay present (Vite or react‑swc), any `console.error`/`pageerror`, or failed document/script/stylesheet requests for the route under test.
- `/main` only: toolbar overlay/occlusion over the canvas; pointer draw failure.
- Required thumbnails missing in the selected mode (left rail or bottom filmstrip).

CDP & reproducibility
- When local flakiness is suspected, run the CDP attach variant: `BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser npm run ux:check:cdp` and attach artifacts.
- If a dev overlay is visible, treat it as a failure and fix before reporting success.
- If intent is ambiguous, propose a one‑line acceptance rule and proceed after acknowledgment.

Definition of Done (UX slice)
- Code compiles (no overlay). Type check passes.
- Route renders without client errors.
- Core interaction works (pointer draw for `/main`).
- Required thumbnails render for the selected mode.
- Screenshot + log attached in `scripts/artifacts/` with explicit paths in the update.

---


## Long‑Running Processes (VS Code)

For a concise playbook (auto‑port servers, robust binds, and URL printing), see `docs/VSCODE_TASK_GUIDE.md`. Keep AGENTS.md short; the guide contains the reusable task patterns and examples.

When the agent needs to run backend/front‑end servers for thorough E2E (CDP/Puppeteer) debugging, do not spawn long‑running processes inside the Codex CLI. Instead, use VS Code Tasks to manage servers that persist independently of the CLI session:

- Use the provided VS Code tasks (see `.vscode/tasks.json`):
  - `Backend: FastAPI (8000)` — runs `python -m extractor.core.scripts.server --host 0.0.0.0 --port 8000`
  - `Prototype: Dev (vite on 8080)` — `npm run dev` (preferred for WS testing)
  - `Prototype: Preview (0.0.0.0:8080)` — `npm run build && npm run preview:8080`
  - `Prototype: E2E Smoke (WS + UI)` — runs `scripts/e2e_smoke.sh` (optional one‑shot)
  - Compound: `Run: Backend + Preview` — launches both servers together

- Ports: VS Code auto‑forwards `8080` (Vite) and `8000` (FastAPI). See `.vscode/settings.json`.

- WebSocket testing: prefer `npm run dev` (Vite dev server) because `vite preview` does not proxy WS by default. In dev, WS `/ws/*` is proxied to the backend in `vite.config.ts`.

- Puppeteer/CDP debugging:
  - Point tests at your live dev servers (e.g., `BASE_URL=http://127.0.0.1:8080/main node scripts/ux_smoke_ws.mjs`).
  - Optional: launch Chrome with `--remote-debugging-port=9222` and attach from VS Code (see `.vscode/launch.json`).
  - Save screenshots/console logs to `scripts/artifacts/` for GitHub Issue evidence.

- Rule: if a workflow requires persistent processes (servers, watchers), always use VS Code tasks to start/stop them. The CLI should run only short‑lived commands (builds, tests, scripts) and Puppeteer against those live servers.

This avoids process‑lifecycle limits and ensures reproducible, thorough E2E debugging with CDP and Puppeteer.

---

## Agent Behavior

* **Be Autonomous**:
  * Rephrase user goal.
  * Outline step plan.
  * Narrate execution so user knows *what* and *why*.

* **Be Persistent**:
  * Keep going until solved.
  * Never hand back incomplete work; research and act if unsure.
  * Make assumptions instead of asking mid-flow; document afterward.

* **Amend Prompt & Tasks**:
  * After finishing, reflect: what was missing in the prompt or task?
  * Suggest prompt/task improvements + communication tips.
  * Note what worked well and should be reused in future.

* **Terminal Command Output (Narrow Width)**:
  * Format multi-line shell commands for a ~400px terminal.
  * Use line continuations with `\` at the end of wrapped lines.
  * Group related flags per line; keep each line short and copy/paste-safe.
  * Example pattern:
    ```bash
    PYTHONPATH=$(pwd)/src \
    ARANGO_DATABASE=pdf_knowledge_base_test \
    python -m extractor.pipeline.run_all run \
      --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf \
      --results data/results/pipeline \
      --skip-llm03 --skip-descriptions06 --summary-only07
    ```
  * Prefer environment variables on separate lines above the command; avoid overly long single lines.

---

## Agent Workflow (Tabbed)

Use this system as follows for every UI/API change in the `prototypes/tabbed` app. This keeps our loop fast, objective, and artifact‑driven.

0) Incoming drafts (optional)
   - If the human drops a multi-topic draft under `prototypes/tabbed/issues/incoming/`, run: `Issues: Promote incoming (tabbed)`.
   - This splits the draft into atomic issues under `prototypes/tabbed/issues/` and scaffolds smokes/tasks automatically. The original draft is moved to `incoming/archive/` with back-links.

1) Scaffold an issue and smoke first
   - VS Code: `Issue: Scaffold (tabbed)` (or `make scaffold ISSUE=007 TITLE="label"`)
   - This creates:
     - `prototypes/tabbed/issues/NNN_*.md` (template with Acceptance)
     - `scripts/smokes/issue_NNN.mjs` (failing stub)
     - VS Code task `Smokes: Issue NNN`

2) Normalize acceptance in the issue file
   - Add objective selectors, routes, and expected behavior.
   - Keep acceptance minimal and testable.

3) Implement the smoke (make it fail for the right reason)
   - Fill the stub with selectors/conditions per acceptance.
   - Save artifacts to `scripts/artifacts/`.

4) Implement the minimal code change
   - Prefer non‑blocking UI updates and explicit tooltips/titles.
   - Update only the files necessary; keep patches small.

5) Verify
   - Fast gate: `ruff`, `black --check`, `mypy`, `pytest -q`.
   - API smoke(s): `node scripts/smokes/api_generate_model.mjs`.
   - UX health: `node scripts/ux_check_cdp_auto.mjs`.
   - Live scenarios (preferred): `python scenarios/run_all.py` or `make run-scenarios`.
   - One command local CI: `scripts/ci_local.sh` or `make ci` (verifies dev servers/CDP, runs gates + scenarios, prints artifacts).

6) Record artifacts
   - Paste log + screenshot paths into the issue file under “Artifacts”.

Rules
- Always add/extend at least one smoke per issue.
- Never mark an issue “done” without artifacts from `scripts/artifacts/` and a passing smoke.
- Keep the UI non‑blocking when possible (use the ShadCN loader components in `components/ui/loader.tsx`).

Quick commands
- `make dev`, `make smokes`, `make ci`, `make scaffold ISSUE=008 TITLE="toolbar"`, `make smoke-issue ISSUE=008`.
- VS Code: `Issue: Quick (tabbed)` for simple one‑liner issues (route, selector, contains).

---

## Lessons Learned (Agent Memory)

Use Lessons Learned frequently — it is your persistent memory and the graph search makes it indispensable for unblocking. The flow is fast and local.

- When blocked (triage)
  - Derive a query from your latest log: `make lessons-recall-last TAGS=cdp SCOPE=tabbed`
  - Or run a direct recall: `uv run scripts/lessons/recall_agent.py --q "puppeteer connect hang" --scope tabbed --depth 2 --k 5 --json`
  - Expand via neighbors: `uv run scripts/lessons/related.py --title "…" --scope tabbed`
  - Explore paths: `uv run scripts/lessons/multihop.py --title "…" --scope tabbed --depth 2`

- Before coding (reuse patterns)
  - BM25 recall on your problem statement; read top lessons’ playbooks.
  - If results feel thin, seed or cluster: `make lessons-seed-demo COUNT=50 BATCH=demo_tmp` then `make lessons-propose` (FAISS KNN with rationale gate).

- After solving (capture knowledge)
  - Add your lesson: `uv run scripts/lessons/add.py --title "…" --problem "…" --playbook "…" --tags t1,t2 --scope tabbed`
  - Link solving edges (directional) to helpful prior lessons and approve as needed: `uv run scripts/lessons/approve_edge.py …`.

- Admin + hygiene
  - List edges by status: `uv run scripts/lessons/list_edges.py --status pending --limit 10`
  - Prune stale pending: `make lessons-prune`
  - Delete seeded demos: `make lessons-delete-demo BATCH=demo_tmp`

- Status + HTTP smokes
  - Curated status: `scripts/lessons/LESSONS_FUNCTIONALITY_STATUS.md`
  - Generate test status: `make lessons-status-report` → `scripts/artifacts/lessons_status_report.md`
  - HTTP endpoint smokes (server running): `make lessons-http-smokes`

Best practices
- Treat Lessons Learned as your first stop when stuck; it turns past work into searchable memory.
- Prefer scope‑aligned edges; approve with human rationale to harden the graph.
- Keep demo data separate via `demo=true` and `demo_batch` for easy cleanup.


Incoming commands
- VS Code: `Issues: Promote incoming (tabbed)`
- Make (optional): `make promote-incoming` (add target if needed)

References
- Full workflow: `prototypes/tabbed/docs/workflow.md`.
- Issue template: `prototypes/tabbed/issues/README.md`.


## Prompting & Verification Best Practices

* **System Role**: Always begin with a clear system role/persona (e.g., “You are a meticulous, production-grade Python/React developer. Follow repo conventions exactly.”).
* **Structured Outputs**:
  * Prefer `response_format` or explicit JSON schemas for predictable results.
  * Fail closed: if schema isn’t followed, retry with explicit correction.
  * Document schema expectations in prompts.
* **Verification Loop**:
  * After each patch, rerun lint + tests until passing or a hard blocker is identified.
  * Auto-apply minimal fixes for common errors; rerun without stopping.
* **Reflection**:
  * Capture what worked and what failed.
  * Suggest refinements for future agent runs.
* **Prompt Reuse**:
  * Maintain a library of canonical prompts for recurring tasks.
  * Prefer referencing these over improvising new phrasing.
* **Error Handling**:
  * Retry gracefully on external tool failures (exponential backoff once).
  * Always return actionable next steps; never fail silently.

---

## Development Basics

* **Bootstrap**:
  ```bash
  test -d .venv || uv venv
  source .venv/bin/activate && uv pip install -e .[dev]
  set -a && [ -f .env ] && source .env && set +a
  ```
* **Directly-Run Scripts (Agent Environments)**:
  - When authoring scripts that the agent may invoke directly (outside the project venv), add a uv script metadata header so dependencies resolve automatically in ephemeral environments.
  - Recommended header at the very top of the file (after the shebang or using a uv shebang):
    ```python
    #!/usr/bin/env python3
    # /// script
    # requires-python = ">=3.10"
    # dependencies = [
    #   "typer>=0.16.0",
    #   # add any other runtime deps here
    # ]
    # ///
    ```
  - Run with uv to honor the header: `uv run path/to/script.py ...`
  - Rationale: the agent may not execute within the project’s venv; the uv header ensures a reproducible, self-declared runtime without adding brittle per-host setup.

* **LLM Code Review Bundles (copy_selected_files.py)**
  - Purpose: create a single, LLM-friendly text bundle of relevant source files for review or external analysis.
  - Default behavior: respects `.gitignore` via Git, excludes binaries, enforces per-file and total byte caps, and adds language code fences.
  - Typical commands:
    - Bundle a subtree (e.g., Tabbed prototype):
      - `python3 scripts/tools/copy_selected_files.py --root prototypes/tabbed --output scripts/artifacts/tabbed_bundle.txt`
    - Preview selection only:
      - `python3 scripts/tools/copy_selected_files.py --root prototypes/tabbed --list`
    - Include special filenames/exts (globs):
      - `python3 scripts/tools/copy_selected_files.py --root . --include-ext ".proto,Justfile,vite.config.ts" --output scripts/artifacts/project_bundle.txt`
    - Exclude additional paths:
      - `python3 scripts/tools/copy_selected_files.py --extra-exclude-paths "**/big_fixtures/**,**/*.snap"`
    - Run via uv (auto-resolve deps from script header):
      - `uv run scripts/tools/copy_selected_files.py --root prototypes/tabbed --output scripts/artifacts/tabbed_bundle.txt`
  - Adding a review header/prompt at the top of a bundle:
    - Save the review request to a file, then concatenate:
      - `cat scripts/artifacts/review_header.md scripts/artifacts/tabbed_bundle.txt > scripts/artifacts/tabbed_code_review_bundle.md`
    - Store artifacts under `scripts/artifacts/` and reference exact paths in updates/issues.
  - When to use:
    - Preparing focused code review contexts, summarization, or external model uploads where only a subset of the repo is needed.
  - Notes:
    - Prefer Git-aware defaults (no `--no-respect-gitignore`) to avoid bundling build outputs.
    - Adjust `--max-total-bytes`/`--max-file-bytes` if the bundle is too large; keep sizes practical for the target model.
* **Structure**:
  * `src/lean4_prover/` → core Python
  * `frontend/` → React + TypeScript + Vite
  * `tests/`, `docs/`, `scripts/`, `workspace/`
* **Frontend**:
  ```bash
  cd frontend && npm run dev | build | preview
  ```
* **Lean/Docker**:
  ```bash
  docker compose up -d --build
  ```

---

## Style & Testing

* **Python**: Black (100 cols), Ruff, type hints via mypy, 4 spaces.
* **Frontend**: Prettier + ESLint, camelCase vars, PascalCase components.
* **Testing**: `pytest -q`; use mocks; keep tests deterministic and fast.
* **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`…).

---

## Security

* Never commit secrets.
* Copy `env.example` → `.env` and fill API keys.
* Verify `.gitignore` before committing.

---

## LLM Provider Sanity Check (SciLLM‑First)

ALWAYS use SciLLM directly for Chutes. Do not route through LiteLLM or other adapters for Chutes calls. No bespoke httpx paths.

Chutes Calls (one‑liner)
- Use the shared helpers: `achutes_text_json()`, `get_text_router()`, `get_vlm_router()`, `chutes_curl_chat_json()`.
- Order: Router → SDK → curl. Curl fallback is mandatory and must save artifacts.
- Force curl globally when stabilizing: `export SCILLM_FORCE_CURL=1`.
- Keep two alternates per model via `CHUTES_*_ALT{1,2}`.

See the compact policy and examples in docs/LLM_CHUTES_POLICY.md and SCILLM_USAGE.md.

- Quick guide: see `SCILLM_USAGE.md` for exact env, examples, and fixes.
- Helper (preferred): `src/extractor/pipeline/utils/chutes_scillm.py: chutes_chat_json()`.
- Unset OpenAI envs to avoid Bearer conflicts: `unset OPENAI_API_KEY OPENAI_BASE_URL`.

Quick Doctor (expect `{ "ok": true }` and exit 0):

```bash
source .venv/bin/activate && \
set -a && [ -f .env ] && source .env && set +a && \
SCILLM_AUTOSCALE=${SCILLM_AUTOSCALE:-1} \
python scripts/tools/scillm_quick_doctor.py
```

VS Code Task: run `SciLLM: Quick Doctor` from the Command Palette.

Canonical direct form (if you must call the client directly):

```
from scillm import completion
import os

resp = completion(
  model=os.environ["CHUTES_TEXT_MODEL"],
  api_base=os.environ["CHUTES_API_BASE"].rstrip('/'),
  api_key=None,
  custom_llm_provider="openai_like",
  messages=[{"role":"user","content":"Return only {\"ok\":true} as JSON."}],
  response_format={"type":"json_object"},
  extra_headers={"x-api-key": os.environ["CHUTES_API_KEY"]},
  timeout=60,
)
```

Troubleshooting (summary; see SCILLM_USAGE.md for details):
- Flip base with/without `/v1` if you see 404.
- Ensure the model id exists in `GET $CHUTES_API_BASE/models` for your tenant.
- Keep `api_key=None` and supply `x-api-key` in `extra_headers` exactly once.

---

## Ports & Docker (Dev Server Conflicts)

When Vite (8080) or FastAPI (8000/8001) fail to bind, check for conflicts:

- Inspect listeners:
  - `ss -ltnp | rg ':8001\b'` (or `:8000`, `:8080`)
  - `lsof -iTCP:8001 -sTCP:LISTEN -n -P`
  - `fuser -v -n tcp 8001`

- Check running containers and published ports:
  - `docker ps --format '{{.ID}}  {{.Ports}}  {{.Names}}'`
  - Stop containers that publish 8000/8001/8080 if they conflict.

- Use the dev helper (has robust port killer + fallback):
  - `./scripts/dev.sh` (kills 8080/8001, starts backend+Vite)
  - Fallback to 8000: `BACK_PORT=8000 ./scripts/dev.sh`

- Verify health endpoints through Vite proxy or direct:
  - `curl -fsS http://127.0.0.1:8080/api/health/llm | jq`
  - `curl -fsS http://127.0.0.1:8001/api/health/llm | jq`

Tip: Smokes fail fast if `/api/health/llm` isn’t OK. Configure `CHUTES_TEXT_MODEL`/`CHUTES_VLM_MODEL` and Chutes keys in `.env`.

Alternative (raw OpenAI curl) if you specifically need to bypass LiteLLM:

```bash
source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a
curl -sS \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/chat/completions \
  -d '{
        "model": "gpt-4o-mini",
        "messages": [{"role":"user","content":"Return only {\"ok\":true} as JSON."}],
        "response_format": {"type":"json_object"},
        "max_tokens": 20
      }'
```


### Tabbed UI Change Gate (must follow for every UI patch)

- Micro-iterations only: make one UI change at a time. After each change:
  - `npm run typecheck` (prototypes/tabbed/html)
  - `BASE_URL=http://127.0.0.1:8080/main npm run ux:check`
  - If the change touched a specific pane or control, run its DOM smoke:
    - Inspector pane: `node scripts/smokes/ui_inspector_pane_present.mjs`
    - Requirements pane: `node scripts/smokes/ui_requirements_pane_dom.mjs`
- Never batch unrelated JSX edits before a green gate.
- If a Vite overlay appears, immediately revert the last file to last-known-good and re-apply incrementally.
- Smokes must accept a full `BASE_URL` and must not append route suffixes.
