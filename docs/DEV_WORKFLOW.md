# Frictionless Frontend + Backend Workflow (with Codex)

This repo hosts a FastAPI backend and multiple frontend apps (Next.js and Vite React). The setup below keeps dev fast, hot-reloading, and consistent — optimized for Codex CLI.

## Quickstart

- Backend: `make dev-backend` (FastAPI on `http://localhost:8000`)
- Next.js app: `make dev-web` (Gold Annotator on `http://localhost:3000`)
- Vite prototype: `make dev-proto` (on `http://localhost:8080`)
- Both backend + Next.js together: `make dev-all`

Env vars are loaded from the repo’s `.env` for the backend. Frontends proxy API calls via:
- Next.js: `NEXT_PUBLIC_API_PROXY` (default `http://localhost:8000`)
- Vite: `VITE_API_PROXY` (default `http://localhost:8000`)

## VSCode Workspace

Open `extractor.code-workspace` for a multi-root workspace with:
- `src/extractor` (Backend)
- `tools/gold_annotator_web` (Next.js)
- `prototypes/tabbed/html` (Vite React)

## Lint, Format, Test, Types

- Lint: `make lint` (ruff over `src`/`tests`)
- Format: `make format` (black over `src`/`tests`/`scripts`)
- Tests: `make test`
- Types: `make typecheck`

The Python tooling excludes legacy/proto/node dirs to reduce noise. See `pyproject.toml`.

## UX Checks with Codex

Use MCP Puppeteer to validate UI flows and capture screenshots. Typical loop:
1. Run `make dev-all`
2. In Codex, navigate to `http://localhost:3000` and perform interactions
3. Save screenshots to `screenshots/` and iterate on UI

## LLM Provider Sanity

Run the unified adapter check (LiteLLM):

```bash
source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a
python src/extractor/pipeline/utils/litellm_call.py sanity --wrap-json --model "${LITELLM_MODEL:-gpt-4o-mini}"
```

## Notes

- Next.js proxies `/api/:path*` -> backend; Vite proxies `/api/*` -> backend. Call `/api/marker` from the browser.
- To add frontend env vars, prefer `NEXT_PUBLIC_*` and `VITE_*` prefixes. Avoid leaking secrets to clients.

