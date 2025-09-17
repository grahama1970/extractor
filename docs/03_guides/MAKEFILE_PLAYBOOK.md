Makefile Playbook (Cross‑Project)
=================================

Purpose
-------
A practical, reusable guide for Makefiles that agents and humans can apply across projects. Focuses on fast feedback, clear targets, and predictable local/CI flows.

Design Principles
-----------------
- Idempotent: targets safe to re‑run; avoid destructive side effects.
- Explicit: short, descriptive names; log what’s happening.
- Fail‑fast: chain steps with `&&` so failures stop early.
- Composable: small targets that combine into larger flows (e.g., `ci`).
- Portable: avoid project‑specific tooling by default; gate optional steps.
- Discoverable: `make help` lists the most useful targets.

Naming Conventions
------------------
- Use hyphenated verbs/nouns for clarity: `smoke-ui`, `smoke-api`, `lint`, `type`.
- Group with prefixes: `api-*`, `ux-*`, `smoke-*`, `docker-*`, `lessons-*`, `pipeline-*`.
- Declare `.PHONY` for all non‑file targets to avoid timestamp collisions.

Environment Variable Patterns
-----------------------------
- Provide sensible defaults, allow overrides:
  - `BASE_URL ?= http://127.0.0.1:8080`
  - `PY ?= .venv/bin/python`
  - `PYTEST ?= pytest`
- Pass env to subprocesses where relevant (e.g., `BASE_URL=$(BASE_URL) node ...`).
- Keep variable names consistent across repos (`BASE_URL`, `CDP_URL`, `PY`, `PYTEST`).

Core Target Patterns
--------------------
- `help`: echo common targets and one‑line descriptions.
- `setup`: create venv and install dev deps (prefer `uv` when present).
- `setup-smokes`: lean venv for runtime/smoke deps only.
- Fast gates: `lint` (ruff), `fmt` (black --check), `type` (mypy), `test` (pytest -q).
- Dev loop: `dev` (start servers), `stop` (free ports).
- Smokes: `smokes` (full suite), `smoke-ui`, `smoke-api`, small aliases like `coco-export`.
- CI: a single entrypoint that orchestrates checks/smokes and saves artifacts.
- Docker/Compose helpers: `services-up`, `services-down` guarded by docker availability.

Templates (Copy‑Paste)
----------------------
Minimal skeleton:

```make
BASE_URL ?= http://127.0.0.1:8080
CDP_URL  ?= http://127.0.0.1:3000/json/version
PY       ?= .venv/bin/python
PYTEST   ?= pytest

.PHONY: help setup setup-smokes dev stop lint fmt type test smoke-api smoke-ui smokes ci

help:
	@echo "make setup            # venv + dev deps"
	@echo "make setup-smokes     # lean env for smokes"
	@echo "make dev              # start local servers"
	@echo "make stop             # stop local servers"
	@echo "make lint fmt type    # fast gates"
	@echo "make smoke-api        # backend API smokes"
	@echo "make smoke-ui         # UI/CDP smokes"
	@echo "make smokes           # full suite"
	@echo "make ci               # local CI gate"

setup:
	@if command -v uv >/dev/null 2>&1; then \
		uv venv; . .venv/bin/activate && uv pip install -e .[dev]; \
	else \
		python3 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e .[dev]; \
	fi

setup-smokes:
	python3 -m venv .venv && . .venv/bin/activate && \
		python -m ensurepip --upgrade && pip install -U pip && \
		pip install -r requirements-smokes.txt || true

lint:
	- ruff check .
fmt:
	- black --check .
type:
	- mypy src || true

test:
	- $(PYTEST) -q

smoke-api:
	node scripts/smokes/api_basic.mjs

smoke-ui:
	BASE_URL=$(BASE_URL) BROWSERLESS_DISCOVERY_URL=$(CDP_URL) node scripts/smokes/all.mjs

smokes:
	BASE_URL=$(BASE_URL) BROWSERLESS_DISCOVERY_URL=$(CDP_URL) node scripts/smokes/all.mjs

ci:
	BASE_URL=$(BASE_URL) BROWSERLESS_DISCOVERY_URL=$(CDP_URL) bash scripts/ci_local.sh
```

Node smoke (API) example:

```js
// scripts/smokes/api_basic.mjs
import assert from 'node:assert/strict';
const API = process.env.API_BASE || 'http://127.0.0.1:8000';
const r = await fetch(API + '/api/health');
assert.equal(r.ok, true);
console.log('api_basic: OK');
```

Python smoke example:

```bash
# scripts/smokes/smoke_example.py
#!/usr/bin/env python3
import sys, requests
resp = requests.get('http://127.0.0.1:8000/api/health', timeout=5)
assert resp.ok, 'health not ok'
print('smoke_example: OK')
```

Docker CI Parity (Optional)
---------------------------
- Mirror CI inside a container when you need absolute parity with GitHub Actions:
  - `make -f local/docker/Makefile ci`
  - Consider `ci-continue` (don’t stop on first pytest failure) and `ci-logs`.
- Keep this in a `local/` subtree to avoid polluting project root.

Cross‑Platform Notes
--------------------
- Use POSIX sh features (`&&`, `|| true`, `;`) and avoid Bash‑specific syntax in recipes when possible.
- Keep line continuations with `\` and indent with tabs (Make requirement).
- Prefer Python/Node utilities for portability over platform‑specific tools.

Conventions & Hygiene
---------------------
- `.PHONY` for non‑file targets.
- Idempotent targets (e.g., `mkdir -p`, tolerate missing files with `|| true`).
- Clear banners/logging (`@echo` with emojis/checks) to scan logs quickly.
- Short timeouts for smokes; fail fast with actionable messages.

Checklist: Adding a New Target
------------------------------
1) Name: descriptive, grouped (e.g., `smoke-api-coco`).
2) Add to `.PHONY` set.
3) Add one line to `help`.
4) Keep the recipe ≤ 5 lines; factor complexity into scripts.
5) Ensure it’s idempotent and portable.

Troubleshooting
---------------
- Ports busy → `make stop`, verify with `lsof -i :PORT`.
- Venv not activated → use absolute interpreter var `$(PY)`.
- Missing deps → offer `setup-smokes` and bail with a helpful message.
- CI parity drift → pin versions or run inside container (Docker Makefile).

References
----------
- Example: Extractor repo Makefile (local dev + smokes) — see `docs/MAKEFILE_GUIDE.md`
- Example: litellm/local Makefile (Docker CI parity + Helm)
- GNU Make manual: https://www.gnu.org/software/make/manual/make.html
