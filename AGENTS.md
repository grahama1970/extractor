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
* **Research**:
  * If blocked, perform external web research for visuals or code.
  * Use Context7 MCP for modern documentation.
* **Hot Reloading**: All UX must hot-reload for near real-time feedback.
* **User Collaboration**: Implement user requests unless they add brittleness or reduce usability. Recommend against with justification if so.

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

---

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

## LLM Provider Sanity Check

Prefer validating through the same path the codebase uses: `src/extractor/pipeline/utils/litellm_call.py` (LiteLLM Router). This exercises auth, routing, and our multimodal prep.

Basic check (prints JSON and succeeds if it contains `{"ok":true}`):

```bash
source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a
python src/extractor/pipeline/utils/litellm_call.py sanity --model "${LITELLM_MODEL:-gpt-4o-mini}"
```

Expect: output JSON includes `{"ok":true}` (the adapter may add a `metadata` object). Exit code 0 on success, non‑zero otherwise.

Debug variant (always JSON, includes error/usage metadata on failure):

```bash
python src/extractor/pipeline/utils/litellm_call.py sanity --wrap-json --model "${LITELLM_MODEL:-gpt-4o-mini}"
```

Notes:
- Set provider creds in `.env` (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OLLAMA_BASE_URL`, etc.).
- Optionally set `LITELLM_MODEL` in `.env` to your default model.
- For batch/JSONL tests, see `--stdin` and `--jsonl` in the script help.

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
