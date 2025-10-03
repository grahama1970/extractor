# Pipeline Status Summary (agent handoff)

Updated by agent before restart. This note summarizes what changed, what still needs to be done, and how to verify the environment so we can debug with real network/DB calls.

## What’s Implemented

- Stage 09 (section_summarizer)
  - Reworked to use the shared `extractor.pipeline.utils.litellm_call.litellm_call` runner (removed direct `litellm` and the aspirational `aresponses` path).
  - Keeps rolling-window behavior and output format. Typer CLI unchanged (run + debug-bundle).

- Stage 01 (annotation_processor)
  - Invalid JSON now logs as error and increments `errors_count`; adds diagnostic `llm_invalid_json`.
  - Removed duplicate re-initialization of `run_id`/diagnostics/counters.
  - CLI default model aligned with dataclass default: `openai/gpt-4o-mini`.

- Stage 03 (suspicious_headers)
  - Added stub `_retrieve_prior_decisions(...) -> list[dict]` to avoid `NameError` when `--use-prior` is true. Intended for later DB-backed retrieval.

- Stage 07 (reflow_section)
  - `debug-bundle` now initializes required timing/diagnostic variables to avoid `NameError` paths.

- Stage 08 (lean4_theorem_prover)
  - Removed duplicate fallback `__main__` block referencing `_HAS_TYPER`.
  - Leaves Typer-only entrypoint.

- CLI consistency
  - Steps 01–12, 14: confirmed presence of Typer CLI commands `run` and `debug-bundle` and a single `if __name__ == "__main__": app()` entry.

## In-Progress/Deferred Improvements

- 003 Refactor plan (recommended):
  - Move all step logic into import-safe `run(...)` / `debug_bundle(...)` functions (stdlib-only imports at top).
  - Import Typer only inside `if __name__ == "__main__":` and wire thin wrappers to call the same functions. No import-time side effects.
  - Phases:
    1) Convert 09–12 first (quick wins), returning `Path` to outputs.
    2) Convert 06–08 (gate lean4/arango/faiss imports inside call sites).
    3) Convert 01–05 and 14 (add batching + strict JSON parse to 01; harden MP queue in 02).
  - Optional: add `src/extractor/function_runner.py` to invoke any `module:function` via `--call` + JSON.

- Utils import-time guards:
  - Where optional deps exist (faiss/arango/etc.), keep imports inside runtime branches to avoid import-time failures in constrained environments.

## Environment Requirements to Debug with Real Calls

The agent requires network access and env pass-through. The user updated `~/.codex/config.toml`. For reference, the key settings should be:

- `[cli]`:
  - `workdir = "/home/graham/workspace/experiments/extractor"`
  - `approval = "on-request"` (or `"never"`)
  - `sandbox = "workspace-write"`
  - `inherit_env = true`
  - `env_allowlist` includes: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OLLAMA_BASE_URL`, `OLLAMA_API_KEY`, `LITELLM_MODEL`, `LITELLM_DEFAULT_MODEL`, `DEFAULT_LITELLM_MODEL`, `LITELLM_SMALL_MODEL`, `ARANGO_HOST`, `ARANGO_PORT`, `ARANGO_USER`, `ARANGO_USERNAME`, `ARANGO_PASS`, `ARANGO_DATABASE`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `VIRTUAL_ENV`, `PATH`, `PYTHONPATH`.
- `[timeouts]`: `timeout_sec = 900`, `idle_timeout_sec = 0`
- `[policies]`: `allow_network = true`

## Quick Verification (post-restart)

Run these to confirm environment allows network + DB calls. Replace `codex` with your launcher if different.

1) Env + Network
- `codex exec -- bash -lc 'python -c "import os; print(bool(os.getenv("OPENAI_API_KEY")))"'`
  - Expect: `True`
- `codex exec -- bash -lc 'curl -sS -o /dev/null -w "%{http_code}
" https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"'`
  - Expect: `200` (valid key) or `401` (network OK, invalid key)

2) Arango (if running on localhost:8529)
- `codex exec -- bash -lc 'curl -sS http://$ARANGO_HOST:$ARANGO_PORT/_db/_system/_api/version | cat'`
  - Expect: version JSON

## Next Steps (agent after restart)

1) Validate network/DB with the quick checks above.
2) Run small canaries:
   - Stage 09 debug-bundle with a tiny bundle → confirm `09_summaries.json` write.
   - Stage 10 debug-bundle `--skip-export` → confirm `10_flattened_data.json` write.
3) If successful, proceed with 003 Refactor Phase 1 (09–12):
   - Extract `run(...)` + `debug_bundle(...)` to import-safe functions, wire Typer under `__main__`.
   - Keep JSON outputs and file paths unchanged.
4) Optionally add `function_runner.py` for generic `module:function` JSON invocations.

## Known Risks / Open Items

- Some utils and tools still import Typer at top-level. These should be main-guarded if they block test imports.
- FAISS/Arango/Lean4 imports should be gated in runtime branches to avoid import-time failures in constrained environments.
- Ensure `.env` keys exist in your venv session or are exported in the shell; Codex config only passes through what exists.

---

This note is intended as a handoff. After restart, I’ll use it as the starting checklist to validate the environment and continue the refactor + debugging with real network/DB calls.
