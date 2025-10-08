SciLLM Migration Guide (from LiteLLM) — Troubleshooting‑First

  This guide explains how to transition a Python codebase from LiteLLM
  to SciLLM (a fork that remains API‑compatible) with minimal churn.
  It focuses on avoiding common pitfalls, verifying correctness, and
  keeping debugging easy.

  Scope

  - Keep PyPI litellm available for dev debugging.
  - Prefer SciLLM at runtime (local fork or VCS URL).
  - Migrate env usage to SCILLM_* while preserving LITELLM_* fallbacks.
  - Adopt SciLLM Router + parallel_acompletions as the default fast
    path.
  - Provide self‑check, smoke tests, and CI fail‑fast diagnostics.

  ———

  Why SciLLM

  - API‑compatible with LiteLLM; adds Router + parallel batching, image
    compression, and research‑friendly helpers.
  - Works with OpenAI‑compatible gateways (CHUTES/OpenAI), local, or
    hybrid providers.

  ———

  Quick Migration Steps

  - Installation (least risk)
      - Keep litellm installed in your dev venv for debugging.
      - Add SciLLM via editable local path (dev) or direct file URL
        (stable):
          - uv pip install -e /home/graham/workspace/experiments/litellm
          - or uv pip install "scillm @ file:///home/graham/workspace/
            experiments/litellm"
  - Keep imports unchanged (no code churn)
      - Still import from litellm at runtime:
          - from litellm import Router, completion,
            parallel_acompletions
      - SciLLM provides the litellm module under the scillm
        distribution.
  - Prefer SciLLM at runtime (dev override)
      - Add a safe sitecustomize dev toggle so import litellm resolves
        to your local SciLLM checkout:
          - export SCILLM_DEV_PATH=/home/graham/workspace/experiments/
            litellm
          - Python auto‑loads sitecustomize; we prepend SCILLM_DEV_PATH
            to sys.path.
          - Unset SCILLM_DEV_PATH to test PyPI litellm without changing
            your venv.
  - Model selection precedence (explicit wins)
      - --model flag
      - GM_LLM_MODEL
      - SCILLM_SMALL_TEXT_MODEL → SCILLM_DEFAULT_MODEL
      - LITELLM_SMALL_TEXT_MODEL → LITELLM_DEFAULT_MODEL
      - Fallback
  - Router + parallel defaults (fast path)
      - If SCILLM_ROUTER_MODELS is set, auto‑enable parallel batching
        unless GM_LLM_PARALLEL=0.
      - Otherwise, use --parallel or GM_LLM_PARALLEL=1.

  ———

  Project Changes We Made (Patterns to Copy)

  - Central model resolver
      - resolve_model(preferred) returns (model, source), enforcing
        precedence.
      - call_llm_json(..., model=...) accepts explicit model and logs:
          - llm.select: {selected_model, source, api_base_present,
            profile, request_id}
  - Clean OpenAI‑compatible routing
      - Pass api_base/api_key explicitly when present.
      - Don’t force response_format for custom providers.
  - Parallel adapter (batch)
      - call_llm_json_parallel(prompts | prompt, ...) supports:
          - Single string or list of prompts.
          - Raw OpenAI responses and {request, response} objects (both
            shapes).
          - One‑pass selective retry for per‑item errors via single‑call
            fallback.
  - CLI/MCP parity
      - All LLM‑using CLIs accept --model and --profile (fast/accurate).
      - Anchor scoring (llm-score-anchor) and QA LLM (generate-qa-llm)
        accept --parallel and --batch-size.
      - MCP tools forward model and parallel flags to the CLI.
  - Happy Path untouched by default
      - Propose → llm-score remains unchanged by default; parallel is
        auto‑enabled only when Router is present.

  ———

  Verification & Self‑Tests (No Network)

  - Self‑check command (prints JSON)
      - uv run lessons-relations llm-selfcheck
      - Outputs: litellm import path, SciLLM Router/parallel
        availability, Router env present, resolved model + source.
  - Dry smoke (Router/parallel only)
      - SCILLM_ROUTER_MODELS='["openai/zai-org/GLM-4.5-Air","openai/zai-
        org/GLM-4.6-turbo"]'
      - SCILLM_SMOKE_DRY=1 python scenarios/
        scillm_router_parallel_smoke.py
      - Confirms Router config and parallel function presence; no
        external calls.
  - CI (fail fast + verbose logs)
      - A small GitHub Actions workflow runs:
          - llm-selfcheck → asserts ok + Router/parallel availability
          - scillm_router_parallel_smoke.py (dry) → asserts ok + Router
            models configured
      - On failure: prints litellm_path, Router configured flag,
        selected model/source, and notes.

  ———

  Common Pitfalls & Fixes

  - “Imports still resolve to PyPI litellm”
      - Use SCILLM_DEV_PATH to prefer local SciLLM checkout.
      - Or uninstall PyPI litellm then install scillm (dist) pointing at
        your fork.
      - Verify: python -c "import litellm,inspect;
        print(inspect.getfile(litellm))"
  - “Router silently not used; no speedup”
      - Ensure SCILLM_ROUTER_MODELS is set (JSON or comma-separated).
      - Parallel is auto‑enabled unless GM_LLM_PARALLEL=0.
      - Confirm with llm-selfcheck: router_models_configured should
        be true.
  - “Blocked expensive provider still used”
      - We only apply blocklist fallback when --model is not provided.
      - If you forced --model, we don’t override it; this is by design.
      - Set model via env or remove --model to allow fallback.
  - “Direct file URL not working”
      - Use three slashes: file:///home/… not file:////home/….
      - PEP 508 form in pyproject: "scillm @ file:///abs/path/to/
        litellm"
  - “Conflicting installs in one venv”
      - For reproducibility, install only scillm in CI.
      - Keep PyPI litellm only in dev venvs if you must debug upstream
        behavior.

  ———

  Suggested Checklists

  - Local dev (single venv, dual import modes)
      - Install scillm extra (and optionally keep litellm)
      - export SCILLM_DEV_PATH=/abs/path/to/litellm
      - Check import path → local
      - Router models env → make scillm-smoke (dry)
      - Live calls only after validating gateway base/key
  - CI
      - Install scillm from your GitHub fork/URL (no PyPI litellm)
      - Run llm-selfcheck and scillm smoke (dry)
      - Optionally run a minimal anchor/edge batch against a mock
        provider or gateway sandbox

  ———

  Minimal CI Snippet (Fail Fast)

  - Run json self-check
  - Print import path and selected model source
  - Dry smoke (no network)
  - Exit non‑zero with useful diagnostics if any check fails

  ———

  Rollback Plan

  - Unset SCILLM_DEV_PATH (dev mode falls back to PyPI litellm).
  - In CI, pin scillm back to a known commit or remove it to revert to
    PyPI litellm quickly.
  - Since imports remain from litellm, no call‑site code needs changing.

  ———

  FAQ

  - “Why keep litellm at all?”
      - It’s useful for debugging and to compare behavior. The dev
        override + self‑check ensures clarity on which one you’re using.
  - “Do we need to rename imports to scillm?”
      - No. The scillm distribution provides the litellm package. Keep
        imports stable (from litellm import …).
  - “How do we control speed vs accuracy?”
      - Use per‑task --profile fast|accurate (or GM_LLM_PROFILE_* envs),
        and --model flags for exact model control.

  ———

  Final Notes

  - Start with SCILLM_DEV_PATH in dev for quick iteration.
  - Switch to scillm (distribution) only in CI for reproducibility.
  - Rely on llm-selfcheck and the dry smoke as the first step in any
    pipeline to fail fast and give clear import/source diagnostics.