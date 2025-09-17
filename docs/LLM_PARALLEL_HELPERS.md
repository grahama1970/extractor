# LiteLLM Parallel Helpers (Router)

This project integrates an optional client-side concurrency helper for LiteLLM Router.
It mirrors the proposed upstream `litellm/router_utils/parallel_acompletion.py` API
but does not require the upstream PR to be merged.

Key points
- No behavior change to callers of `litellm_call` (same function, same return shape).
- If the upstream helper exists, it is used. Otherwise, we transparently fall back to a
  vendored copy at `src/extractor/pipeline/utils/vendor_parallel_acompletion.py`.
- If neither is usable, `litellm_call` uses the original legacy path with
  `asyncio.as_completed` without additional client-side helper.
- Feature flag: set `LITELLM_PARALLEL_DISABLE=true` to force the legacy path even if
  helpers are available.

Environment variables
- `LITELLM_PARALLEL_DISABLE=true` → disable helper path (use legacy path)
- `LITELLM_MAX_PARALLEL` → default Router per-deployment semaphore
- `LITELLM_NUM_RETRIES` → default Router retries

Smoke test
- The smoke test avoids network calls by patching the Router with a fake async router.
- Run both paths:

```
python scripts/smoke_litellm_parallel.py --mode helper
python scripts/smoke_litellm_parallel.py --mode legacy
```

Expected:
- Both runs print JSON like:

```
{"mode": "helper", "have_helpers": true, "helpers_disabled": false, "ok": true, "answers": ["ok"]}
{"mode": "legacy", "have_helpers": true, "helpers_disabled": true, "ok": true, "answers": ["ok"]}
```

Notes
- This smoke script is not part of the automated test suite and should be run ad hoc.
- Provider keys are not required; it does not call external APIs.
- When using `litellm_call` normally, set provider env vars as usual (e.g., `OPENAI_API_KEY`).

