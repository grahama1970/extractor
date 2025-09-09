# Repository Guidelines

## Agent Quickstart (Codex CLI)

- Activation: Start by telling the agent: `Activate the current dir as project using serena`. This binds the workspace and enables Serena tools.
- Planning: For multi-step work, use the plan tool (`update_plan`) to track progress.
- Editing: Make changes via `apply_patch` with minimal, targeted diffs.
- Search: Prefer `rg` (ripgrep) for fast code/text search.
- Verify: Run `pytest -q`, `ruff check .`, `black .`, and `mypy src` as needed.

### Always Do This First

- Activate Serena project: tell the agent `Activate the current dir as project using serena`.
- Activate venv and load env for each command: `source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a`.

### One-shot Examples

- Bootstrap + tests: `test -d .venv || uv venv; source .venv/bin/activate && uv pip install -e .[dev] && set -a && [ -f .env ] && source .env && set +a && pytest -q`.
- Bootstrap + CLI: `test -d .venv || uv venv; source .venv/bin/activate && uv pip install -e .[dev] && set -a && [ -f .env ] && source .env && set +a && lean4-agent --no-db --no-cache requirement "The sum of two even numbers is even"`.

### Bootstrap Environment

- cd: `cd /path/to/lean4` (Codex may already be there; include if unsure).
- Create venv: `uv venv` (or `python -m venv .venv`).
- Activate venv: `source .venv/bin/activate`.
- Install deps: `uv pip install -e .[dev]` (or `pip install -e .[dev]`).
- Load env: `set -a; [ -f .env ] && source .env; set +a`.
- Inspect project: skim `pyproject.toml` (project metadata, deps, tools).

Note: Shell state is not guaranteed to persist across Codex calls. When running a command that relies on venv or env vars, chain activation and the command in one line, e.g.: `source .venv/bin/activate && set -a && source .env && set +a && pytest -q`.

## Project Structure & Module Organization

- src/lean4_prover/: Core Python package (core, config, utils, concurrency, db,
websocket).
- tests/: Pytest suite (tests/unit, tests/test_cli.py).
- frontend/: Vite + React + TypeScript UI.
- docs/: Architecture, usage, and reports.
- scripts/: Dev utilities and CLI demos.
- workspace/: Mounted into the Lean container for compiled assets.
- Dockerfile, docker-compose.yml: Lean 4 + Mathlib environment (pinned to v4.8.0).
- lakefile.toml, lean-toolchain: Lean project metadata.

## Build, Test, and Development Commands

- Python install:
    - uv pip install -e .[dev] (preferred) or pip install -e .[dev]
- Run CLI:
    - lean4-agent --no-db --no-cache requirement "The sum of two even numbers
is even"
- WebSocket server:
    - certainly-server
- Frontend:
    - cd frontend && npm run dev | build | preview
- Lean environment:
    - docker-compose up -d --build
- Lint/format/type-check:
    - ruff check . • black . • mypy src

## Coding Style & Naming Conventions

- Python: 4 spaces; Black (line length 100); Ruff for linting; imports sorted by
Ruff/isort; type hints encouraged (mypy permissive).
- Naming: snake_case (functions/vars), PascalCase (classes), UPPER_SNAKE_CASE
(constants).
- Frontend: Prettier + ESLint; camelCase for vars/functions, PascalCase for React
components.

## Testing Guidelines

- Framework: pytest (+ pytest-asyncio).
- Run: pytest -q or pytest --cov=src/lean4_prover.
- Layout: tests live in tests/unit and follow test_*.py.
- Practices: mock external services; prefer --no-db --no-cache in CLI paths; keep
tests deterministic and fast.

## Commit & Pull Request Guidelines

- Commits: imperative mood, concise subject; prefer Conventional Commits (feat:,
fix:, refactor:, docs:, test:, chore:). Example: feat(core): add input router
fallback.
- PRs: clear description, link issues, include test updates; ensure pytest,
ruff, and black pass; add screenshots for UI changes; update docs/ when behavior
changes.

## Security & Configuration Tips

- Environment: cp env.example .env and set API keys (LLM providers) and optional
ArangoDB/Redis; never commit secrets.
- Docker: resources configured in docker-compose.yml (lean_runner mounts ./
workspace).
- Secrets and logs: avoid adding sensitive files; verify .gitignore entries before
committing.

## LLM Provider Sanity Check (curl‑first)

Use this quick runbook when LLM calls fail (401, non‑JSON, empty content) before digging into code:

1) Activate venv and export env
- `source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a`

2) Verify key is in current shell (env overrides .env)
- Never paste secrets into logs or commits.

3) curl JSON‑mode sanity test (OpenAI)
- `export OPENAI_API_KEY=sk-...` (temporary in shell)
- Run:
```
curl -sS \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/chat/completions \
  -d '{
        "model": "gpt-4o-mini",
        "messages": [{"role":"user","content":"Return only {\\"ok\\":true} as JSON."}],
        "response_format": {"type":"json_object"},
        "max_tokens": 20
      }'
```
- Expect HTTP 200 and `{"ok":true}`.

4) Model quirks
- GPT‑5 requires `temperature=1.0`. If using gpt‑5/gpt‑5‑mini with LiteLLM, set temp accordingly.
- Prefer models with reliable JSON mode (e.g., `openai/gpt-4o`) for strict JSON stages.

5) LiteLLM tips
- Add a system message instructing JSON‑only output.
- Consider the OpenAI Responses API for stricter JSON compliance.

6) Fallback playbook
- If curl fails → fix key/org/project.
- If curl passes but code fails → check model ID, temperature, response_format, and network/proxy.
- Use `scripts/test_summarizer_json_mode.py` for quick JSON‑mode testing outside the pipeline.

See also: `scripts/curl_json_mode_check.sh` for a one‑command curl sanity check.
