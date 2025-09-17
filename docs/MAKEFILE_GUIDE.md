Makefile Guide
===============

This guide explains how to use and extend the repository Makefile for local development, smokes, and quick CI-like gates. Targets are designed to be fast, explicit, and composable.

Quick Start
-----------

- Bootstrap a full dev venv and install dev extras:
  - `make setup`
- Minimal venv for running smokes only (leaner deps):
  - `make setup-smokes`
- Start dev (backend + Vite proxy):
  - `make dev`
- Stop servers bound to common ports (8080/8001):
  - `make stop`
- Run local CI gate (server checks + full smokes):
  - `make ci`

Environment Variables
---------------------

- `BASE_URL` (default `http://127.0.0.1:8080`): UI/dev server base.
- `CDP_URL` (default `http://127.0.0.1:3000/json/version`): Browserless/Chrome CDP discovery URL for UX smokes.
- `PY` (default `.venv/bin/python`): Python interpreter used by Makefile.
- `PYTEST` (default `pytest`): Pytest binary for Gamified/lessons tests.
- UI smoke-specific:
  - `SMOKE_URL` (default `http://127.0.0.1:8080/classic`)
  - `CDP_ORIGIN` (default `http://127.0.0.1:9222`)
  - `CDP_TOKEN` (optional)
- ArangoDB targets:
  - `ARANGO_URL`, `ARANGO_DB`, `ARANGO_USER`, `ARANGO_PASS`

Tip: Export these in your shell or pass inline (e.g., `BASE_URL=... make smokes`).

Core Targets
------------

- `help` — Lists common targets and usage.
- `setup` — Creates `.venv` and installs dev extras (uses `uv` if present).
- `setup-smokes` — Lean venv for smoke/runtime deps (includes PyMuPDF, Camelot, LiteLLM). Use when you only need smokes.
- `dev` — Runs `scripts/dev.sh` to launch FastAPI and Vite.
- `stop` — Kills processes on 8080/8001 (best-effort).
- Fast gates:
  - `lint` (ruff), `fmt` (black --check), `type` (mypy), `test` (pytest -q)
- API smokes (no browser):
  - `api-smokes` → runs `scripts/smokes/api_generate_model.mjs`
- UX health (requires CDP):
  - `ux-health` → verifies CDP connectivity and basic UI health
- Full UX smokes (requires servers + CDP):
  - `smokes` → runs `scripts/smokes/all.mjs`
- Local CI gate:
  - `ci` → executes `scripts/ci_local.sh` (server checks + smokes + artifacts)

Issue Workflow Helpers
----------------------

- Scaffold a new issue + smoke:
  - `make scaffold ISSUE=007 TITLE="label button"`
- Run a specific issue smoke:
  - `make smoke-issue ISSUE=007`

LiteLLM Utility Smokes
----------------------

- `smoke-litellm` — Basic sanity smoke (structured call).
- `smoke-litellm-image` — Image URL path.
- `smoke-litellm-all` — Shorthand for the two above.
- `smoke-litellm-results` — Saves structured artifacts from smokes.
- Extended set:
  - `smoke-litellm-local`, `smoke-litellm-stream`, `smoke-litellm-batch`, `smoke-litellm-full`

Pipeline Smokes
---------------

- `smoke-07-reflow-min` — Minimal Stage 07 reflow smoke (results mode).
- Strict sets:
  - `smokes-stage07-strict`, `smokes-stage07-strict-extended`
- Quick end-to-end (gold checks):
  - `quick-pipeline`
- Full pipeline (requires keys/DB):
  - `pipeline-full`

UI Runtime Error Smoke (CDP)
----------------------------

- `smoke-ui` — Playwright CDP console-error smoke against `SMOKE_URL` with `CDP_ORIGIN`.
- `smoke-ui-strict` — Same, exits non-zero and prints artifacts.

Lessons (ArangoDB) Targets
--------------------------

- Setup collections/view: `lessons-setup`
- CRUD/search helpers: `lessons-add`, `lessons-search`, `lessons-delete`, `lessons-link`, `lessons-related`, `lessons-multihop`
- Agent recall helpers: `lessons-recall`, `lessons-recall-last`, `lessons-recall-diff`
- Seed/prune/report: `lessons-seed-demo`, `lessons-delete-demo`, `lessons-status-report`
- HTTP smokes for lessons endpoints: `lessons-http-smokes`

ArangoDB Docker Helpers
-----------------------

- Start/stop local instance: `arango-up`, `arango-down`

Bundling for Code Review
------------------------

- `bundle-tabbed` — Bundles the Tabbed prototype files with a header for LLM code review under `scripts/artifacts/`.

Patterns for Adding Smokes
--------------------------

1) Place your script under `scripts/smokes/` (Node or Python).
2) Add it to `scripts/smokes/all.mjs` to include in the full suite.
3) Optionally add a dedicated Make target if you want a one-liner (follow the `api-smokes` pattern for Node, or use `$(PY)` for Python).

Example (backend API smoke one-liner):

- Target: `api-smokes`
- Command: `BASE_URL=$(BASE_URL) node scripts/smokes/api_generate_model.mjs`

Conventions & Tips
------------------

- Always declare `.PHONY` for non-file targets to avoid timestamp pitfalls.
- Use Make variables for portability:
  - `PY`, `PYTEST` allow swapping interpreters easily.
  - Wrap multi-step commands with `&&` to fail fast.
- Keep targets idempotent and tolerant (e.g., `|| true` on optional steps in setup).
- Prefer small, composable targets over monoliths; larger flows (like `ci`) should orchestrate simpler ones.

Troubleshooting
---------------

- Ports busy (8080/8001): run `make stop` and restart `make dev`.
- Camelot/PyMuPDF missing: run `make setup-smokes` to install lean deps for backend smokes.
- CDP not reachable: set `CDP_URL` for Browserless or run Chrome with `--remote-debugging-port=9222` and use `CDP_ORIGIN`.
- Permissions on Docker (ArangoDB targets): ensure your user can run `docker compose` or use `sudo` as needed.

Common Workflows
----------------

- Fast local gate while iterating on UI:
  - `make ux-health && make smokes`
- Backend-only API validation:
  - `make api-smokes` or directly `node scripts/smokes/api_tabbed_basic.mjs`
- Full local CI sweep (saves artifacts under `scripts/artifacts/`):
  - `make ci`

---

If you need a dedicated Make target for new backend smokes (e.g., a combined API slice), mirror the `api-smokes` pattern to keep the top-level clean.

See also
--------
- Cross-project playbook: `docs/03_guides/MAKEFILE_PLAYBOOK.md` (portable patterns and templates)
